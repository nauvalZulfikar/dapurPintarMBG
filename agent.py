#!/usr/bin/env python3
"""
Agent Mesh — Project Agent (VPS version)
Jalan di host, watch folder project Docker.
"""

import asyncio
import fnmatch
import json
import logging
import os
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Load .env.agent dulu, fallback ke .env
load_dotenv(".env.agent")
load_dotenv(".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.FileHandler("agent.log"), logging.StreamHandler()],
)
log = logging.getLogger("agent")


def load_config() -> dict:
    if not Path(".agent.yaml").exists():
        raise FileNotFoundError(".agent.yaml not found")
    with open(".agent.yaml") as f:
        cfg = yaml.safe_load(f)

    def resolve(v):
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            val = os.getenv(v[2:-1])
            if val is None:
                raise EnvironmentError(f"Env var {v[2:-1]} not set")
            return val
        return v

    def walk(o):
        if isinstance(o, dict): return {k: walk(v) for k, v in o.items()}
        if isinstance(o, list): return [walk(i) for i in o]
        return resolve(o)

    return walk(cfg)


class LocalQueue:
    def __init__(self, path="agent_queue.json"):
        self.path = Path(path)
        self._q = json.loads(self.path.read_text()) if self.path.exists() else []

    def _save(self):
        self.path.write_text(json.dumps(self._q))

    def push(self, e):
        self._q.append(e)
        self._save()

    def flush(self):
        items, self._q = list(self._q), []
        self._save()
        return items

    def size(self): return len(self._q)


class LLMClient:
    PROVIDERS = {
        "groq": {"url": "https://api.groq.com/openai/v1/chat/completions", "key_env": "LLM_API_KEY"},
        "openrouter": {"url": "https://openrouter.ai/api/v1/chat/completions", "key_env": "OPENROUTER_API_KEY"},
        "custom": {"url": os.getenv("CUSTOM_MODEL_URL", ""), "key_env": "CUSTOM_MODEL_KEY"},
    }

    def __init__(self, cfg):
        self.cfg = cfg["llm"]
        self.provider = self.cfg.get("provider", "openrouter")
        self.model = self.cfg.get("model", "deepseek/deepseek-chat-v3-0324")
        self.fallback_provider = self.cfg.get("fallback_provider", "groq")
        self.fallback = self.cfg.get("fallback_model", "llama-3.3-70b-versatile")
        self.max_tokens = self.cfg.get("max_tokens", 4096)
        self.temperature = self.cfg.get("temperature", 0.2)

    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".next", "dist", "build",
                  "venv", ".venv", "vendor", ".cache", "storage", "data", ".nuxt"}
    KEY_FILES = {"package.json", "composer.json", "requirements.txt", "Dockerfile",
                 "docker-compose.yml", "docker-compose.prod.yml", ".env.example",
                 "tsconfig.json", "next.config.js", "next.config.ts",
                 "turbo.json", "pnpm-workspace.yaml", "artisan", "manage.py",
                 "Makefile", "render.yaml", "ecosystem.config.js"}
    CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".vue", ".php", ".go",
                 ".java", ".rb", ".rs", ".css", ".scss", ".html", ".sql",
                 ".prisma", ".graphql", ".yaml", ".yml", ".json", ".toml"}

    # ~4 chars per token estimate
    TOKEN_BUDGET = {
        "smart_files": 20000,
        "explicit_files": 5000,
        "git_diff": 2000,
        "tree": 1000,
        "key_files": 2000,
    }

    def _estimate_tokens(self, text):
        return len(text) // 4

    def _scan_tree(self, root=".", max_depth=None, watch_paths=None):
        """Scan project directory tree. Depth 1-3 fully, 4-5 only in watch paths."""
        if max_depth is None:
            max_depth = self.cfg.get("context", {}).get("tree_depth", 5)
        tree = []
        root_path = Path(root)
        for p in sorted(root_path.rglob("*")):
            rel = p.relative_to(root_path)
            if any(part in self.SKIP_DIRS for part in rel.parts):
                continue
            depth = len(rel.parts)
            if depth > max_depth:
                continue
            # Depth 4+ only in watch paths
            if depth > 3 and watch_paths:
                in_watch = any(str(rel).startswith(wp.rstrip("/")) for wp in watch_paths)
                if not in_watch:
                    continue
            prefix = "  " * (depth - 1) + ("├── " if p.is_file() else "├── ")
            tree.append(f"{prefix}{rel}")
            if len(tree) > 300:
                tree.append("...[truncated]")
                break
        return "\n".join(tree)

    def _smart_files(self, prompt, root=".", watch_paths=None):
        """Extract keywords from prompt and grep source code for relevant files."""
        import re
        import subprocess

        # Extract meaningful keywords (>3 chars, CamelCase, snake_case, file paths)
        words = set()
        # CamelCase identifiers
        words.update(re.findall(r'[A-Z][a-z]+(?:[A-Z][a-z]+)+', prompt))
        # snake_case / kebab-case identifiers
        words.update(re.findall(r'[a-z][a-z0-9]*(?:[_-][a-z0-9]+)+', prompt))
        # File paths
        words.update(re.findall(r'[\w./]+\.\w{1,5}', prompt))
        # Regular words > 3 chars, skip common ones
        skip = {"the", "and", "for", "that", "this", "with", "from", "have", "file",
                "code", "make", "change", "edit", "update", "fix", "add", "remove",
                "please", "should", "would", "could", "yang", "dari", "untuk", "dengan",
                "buat", "ubah", "tambah", "hapus", "ganti", "pake", "pakai", "bikin",
                "tolong", "coba", "lihat", "check", "semua", "sudah", "belum"}
        for w in re.findall(r'\b\w{4,}\b', prompt):
            if w.lower() not in skip:
                words.add(w)

        if not words:
            return []

        # Determine search paths
        search_paths = []
        if watch_paths:
            for wp in watch_paths:
                p = Path(root) / wp
                if p.exists():
                    search_paths.append(str(p))
        if not search_paths:
            search_paths = [root]

        # Build exclude args
        exclude_args = []
        for d in self.SKIP_DIRS:
            exclude_args.extend(["--exclude-dir", d])

        # Grep each keyword, count hits per file
        file_hits = {}
        for keyword in list(words)[:15]:  # cap keywords
            try:
                result = subprocess.run(
                    ["grep", "-rl", "--include=*.py", "--include=*.js", "--include=*.ts",
                     "--include=*.tsx", "--include=*.jsx", "--include=*.vue", "--include=*.php",
                     "--include=*.go", "--include=*.prisma", "--include=*.graphql",
                     *exclude_args, "-i", keyword] + search_paths,
                    capture_output=True, text=True, timeout=3, cwd=root
                )
                for f in result.stdout.strip().splitlines():
                    f = f.strip()
                    if f:
                        file_hits[f] = file_hits.get(f, 0) + 1
            except (subprocess.TimeoutExpired, Exception):
                continue

        # Rank by hit count, return top files
        ranked = sorted(file_hits.items(), key=lambda x: -x[1])
        return [f for f, _ in ranked[:20]]

    def _git_diff(self, root="."):
        """Get git diff HEAD, capped at 80 lines."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True, text=True, timeout=5, cwd=root
            )
            lines = result.stdout.splitlines()[:80]
            if len(result.stdout.splitlines()) > 80:
                lines.append("...[truncated]")
            return "\n".join(lines)
        except Exception:
            return ""

    def _auto_context(self, root=".", token_budget=2000):
        """Auto-read key project files, limited by token budget."""
        parts = []
        max_lines = self.cfg.get("context", {}).get("max_context_lines", 200)
        root_path = Path(root)
        used = 0
        for fname in self.KEY_FILES:
            p = root_path / fname
            if p.exists() and p.is_file():
                try:
                    text = p.read_text(errors="replace")
                    lines = text.splitlines()
                    if len(lines) > max_lines:
                        lines = lines[:max_lines] + ["...[truncated]"]
                    block = f"\n### {fname}\n```\n" + "\n".join(lines) + "\n```"
                    est = self._estimate_tokens(block)
                    if used + est > token_budget:
                        break
                    parts.append(block)
                    used += est
                except Exception:
                    pass
        return "\n".join(parts)

    def _build_system_prompt(self, cfg):
        """Build project-specific system prompt."""
        agent = cfg.get("agent", {})
        name = agent.get("name", agent.get("id", "Unknown"))
        stack = agent.get("stack", "")
        desc = agent.get("description", "")

        # Auto-detect stack from key files if not configured
        if not stack:
            detected = []
            if Path("package.json").exists():
                try:
                    pkg = json.loads(Path("package.json").read_text())
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    if "next" in deps: detected.append("Next.js")
                    if "react" in deps: detected.append("React")
                    if "vue" in deps: detected.append("Vue")
                    if "express" in deps: detected.append("Express")
                    if "prisma" in deps or "@prisma/client" in deps: detected.append("Prisma")
                    if "typescript" in deps: detected.append("TypeScript")
                    if "turbo" in deps or Path("turbo.json").exists(): detected.append("Turborepo")
                except Exception:
                    pass
            if Path("composer.json").exists(): detected.append("Laravel/PHP")
            if Path("requirements.txt").exists(): detected.append("Python")
            if Path("manage.py").exists(): detected.append("Django")
            if Path("Dockerfile").exists(): detected.append("Docker")
            stack = ", ".join(detected) if detected else "Unknown"

        project_info = f"Project: {name}."
        if stack:
            project_info += f" Stack: {stack}."
        if desc:
            project_info += f" {desc}"

        return (
            f"{project_info}\n\n"
            "You are an expert software engineer working on this project. "
            "You have deep knowledge of the project's stack and conventions.\n\n"
            "When modifying files, output the FULL file content using this format:\n"
            "FILE: path/to/file\n```\n<full file content>\n```\n\n"
            "Rules:\n"
            "- Always output the COMPLETE file, not just the changed part\n"
            "- Preserve existing code style, indentation, and conventions\n"
            "- Do not modify files that are not related to the request\n"
            "- For questions or analysis, respond normally with detailed answers\n"
            "- Reference specific file paths and line numbers when explaining"
        )

    def _context(self, files, prompt, cfg):
        """Build context with token budget management."""
        watch_paths = cfg.get("watch", {}).get("paths", ["."])
        include_git_diff = self.cfg.get("context", {}).get("include_git_diff", False)

        parts = [f"## Task\n{prompt}"]
        budget_used = self._estimate_tokens(prompt)

        # Priority 2: Smart context files (grep-based)
        smart_files = self._smart_files(prompt, watch_paths=watch_paths)
        if smart_files:
            smart_parts = []
            smart_budget = self.TOKEN_BUDGET["smart_files"]
            smart_used = 0
            max_lines = self.cfg.get("context", {}).get("max_context_lines", 200)
            for f in smart_files:
                p = Path(f)
                if not p.exists():
                    continue
                try:
                    text = p.read_text(errors="replace")
                    lines = text.splitlines()
                    if len(lines) > max_lines:
                        lines = lines[:max_lines] + ["...[truncated]"]
                    block = f"\n### {f}\n```\n" + "\n".join(lines) + "\n```"
                    est = self._estimate_tokens(block)
                    if smart_used + est > smart_budget:
                        break
                    smart_parts.append(block)
                    smart_used += est
                except Exception:
                    continue
            if smart_parts:
                parts.append("\n## Relevant Source Files (auto-detected)")
                parts.extend(smart_parts)
                budget_used += smart_used

        # Priority 3: Explicit context_files
        if files:
            explicit_parts = []
            explicit_budget = self.TOKEN_BUDGET["explicit_files"]
            explicit_used = 0
            max_lines = self.cfg.get("context", {}).get("max_context_lines", 200)
            for f in files:
                p = Path(f)
                if not p.exists():
                    explicit_parts.append(f"\n[Not found: {f}]")
                    continue
                try:
                    text = p.read_text(errors="replace")
                    lines = text.splitlines()
                    if len(lines) > max_lines:
                        lines = lines[:max_lines] + ["...[truncated]"]
                    block = f"\n### {f}\n```\n" + "\n".join(lines) + "\n```"
                    est = self._estimate_tokens(block)
                    if explicit_used + est > explicit_budget:
                        break
                    explicit_parts.append(block)
                    explicit_used += est
                except Exception:
                    continue
            if explicit_parts:
                parts.append("\n## Requested Files")
                parts.extend(explicit_parts)
                budget_used += explicit_used

        # Priority 4: Git diff
        if include_git_diff:
            diff = self._git_diff()
            if diff:
                diff_est = self._estimate_tokens(diff)
                if diff_est <= self.TOKEN_BUDGET["git_diff"]:
                    # Only include if changed files overlap with smart_files
                    diff_files = {l.split(" b/")[-1] for l in diff.splitlines() if l.startswith("diff --git")}
                    smart_set = set(smart_files)
                    if not smart_files or diff_files & smart_set:
                        parts.append(f"\n## Recent Changes (git diff HEAD)\n```diff\n{diff}\n```")
                        budget_used += diff_est

        # Priority 5: Project tree
        tree = self._scan_tree(watch_paths=watch_paths)
        tree_est = self._estimate_tokens(tree)
        if tree_est <= self.TOKEN_BUDGET["tree"]:
            parts.append(f"\n## Project Structure\n```\n{tree}\n```")
            budget_used += tree_est

        # Priority 6: Key config files (only 2-3 most relevant)
        auto = self._auto_context(token_budget=self.TOKEN_BUDGET["key_files"])
        if auto:
            parts.append("\n## Config Files")
            parts.append(auto)

        return "\n".join(parts)

    async def complete(self, prompt, context_files=None, cfg=None):
        ctx = self._context(context_files or [], prompt, cfg or self.cfg)
        system = self._build_system_prompt(cfg or {})
        messages = [{"role": "system", "content": system}, {"role": "user", "content": ctx}]

        attempts = [(self.provider, self.model)]
        if self.fallback:
            fb_prov = self.fallback_provider or self.provider
            attempts.append((fb_prov, self.fallback))
        # Last resort: free model on openrouter
        if not any(p == "openrouter" and "free" in m for p, m in attempts):
            if os.getenv("OPENROUTER_API_KEY"):
                attempts.append(("openrouter", "meta-llama/llama-3.3-70b-instruct:free"))

        last_error = None
        used_provider = None
        used_model = None
        for prov, model in attempts:
            try:
                log.info(f"LLM call: {prov}/{model}")
                p = self.PROVIDERS[prov]
                url = p["url"]
                if prov == "custom" and not url:
                    continue
                key = os.getenv(p["key_env"])
                if not key:
                    continue
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                if prov == "openrouter":
                    headers["HTTP-Referer"] = "https://agent-mesh"
                async with httpx.AsyncClient(timeout=120) as c:
                    r = await c.post(url, headers=headers, json={
                        "model": model, "messages": messages,
                        "max_tokens": self.max_tokens, "temperature": self.temperature,
                    })
                    r.raise_for_status()
                    data = r.json()
                    used_provider = prov
                    used_model = model
                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    return content, {
                        "provider": used_provider,
                        "model": used_model,
                        "tokens_in": usage.get("prompt_tokens", 0),
                        "tokens_out": usage.get("completion_tokens", 0),
                        "system_prompt": system,
                        "user_input": ctx,
                    }
            except Exception as e:
                last_error = e
                log.warning(f"LLM failed ({prov}/{model}): {e}")
                await asyncio.sleep(2)

        raise RuntimeError(f"All LLM providers failed. Last: {last_error}")


class FileApplier:
    PROTECTED = {".env", ".env.production", ".env.local", ".env.agent", "secrets/"}

    def __init__(self, extra=None):
        self.protected = self.PROTECTED | set(extra or [])

    def apply(self, response):
        results = []
        lines = response.splitlines()
        i = 0
        while i < len(lines):
            if lines[i].strip().startswith("FILE:"):
                path = lines[i].strip()[5:].strip()
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    i += 1
                i += 1
                content = []
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    content.append(lines[i])
                    i += 1
                results.append(self._write(path, "\n".join(content)))
            i += 1
        return results

    def _write(self, path, content):
        p = Path(path)
        for prot in self.protected:
            if str(p) == prot or str(p).startswith(prot):
                log.warning(f"BLOCKED: {path}")
                return {"path": path, "status": "blocked"}
        backup = None
        if p.exists():
            backup = str(p) + f".bak.{int(time.time())}"
            p.rename(backup)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            log.info(f"Written: {path}")
            return {"path": path, "status": "written", "backup": backup}
        except Exception as e:
            if backup and Path(backup).exists():
                Path(backup).rename(path)
            return {"path": path, "status": "error", "error": str(e)}


class OrchestratorClient:
    def __init__(self, cfg, queue):
        orch = cfg["orchestrator"]
        self.base = orch["url"].rstrip("/")
        self.secret = orch["secret"]
        self.timeout = orch.get("timeout_sec", 30)
        self.retries = orch.get("retry_attempts", 3)
        self.pid = cfg["agent"]["id"]
        self.queue = queue
        self._online = True

    def _h(self):
        return {"Authorization": f"Bearer {self.secret}",
                "Content-Type": "application/json", "X-Agent-ID": self.pid}

    async def send(self, event):
        for attempt in range(self.retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as c:
                    r = await c.post(f"{self.base}/events", headers=self._h(), json=event)
                    r.raise_for_status()
                    if not self._online:
                        self._online = True
                        log.info("Reconnected. Flushing queue...")
                        for e in self.queue.flush():
                            await self.send(e)
                    return True
            except Exception as e:
                log.warning(f"Send failed ({attempt+1}): {e}")
                await asyncio.sleep(2 ** attempt)
        self._online = False
        self.queue.push(event)
        return False

    async def update_task(self, tid, status, result):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                await c.patch(f"{self.base}/tasks/{tid}", headers=self._h(),
                              json={"status": status, "result": result})
        except Exception as e:
            log.error(f"Task update failed: {e}")

    async def log_training(self, system_prompt, user_input, assistant_output,
                           task_id, model, project, files_written=0,
                           success=True, tokens_in=0, tokens_out=0):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                await c.post(f"{self.base}/training-data", headers=self._h(), json={
                    "system_prompt": system_prompt,
                    "user_input": user_input,
                    "assistant_output": assistant_output,
                    "task_id": task_id,
                    "model": model,
                    "project": project,
                    "files_written": files_written,
                    "success": success,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                })
        except Exception as e:
            log.warning(f"Training log failed: {e}")

    async def register(self, cfg):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                r = await c.post(f"{self.base}/agents/register", headers=self._h(), json={
                    "id": cfg["agent"]["id"],
                    "name": cfg["agent"].get("name", cfg["agent"]["id"]),
                    "version": cfg["agent"].get("version", "1.0"),
                    "capabilities": ["file_watch", "prompt", "deploy"],
                })
                r.raise_for_status()
                log.info(f"Registered: {cfg['agent']['id']}")
        except Exception as e:
            log.warning(f"Register failed (non-fatal): {e}")

    async def upload_deploy(self, tarball_path: str, deploy_config: dict):
        """Upload project tarball + deploy config to orchestrator."""
        try:
            async with httpx.AsyncClient(timeout=120) as c:
                with open(tarball_path, "rb") as f:
                    r = await c.post(
                        f"{self.base}/deploy/upload/{self.pid}",
                        headers={"Authorization": f"Bearer {self.secret}", "X-Agent-ID": self.pid},
                        files={"file": ("project.tar.gz", f, "application/gzip")},
                        data={"config": json.dumps(deploy_config)},
                    )
                    r.raise_for_status()
                    result = r.json()
                    log.info(f"Deploy upload accepted: {result}")
                    return result
        except Exception as e:
            log.error(f"Deploy upload failed: {e}")
            raise

    async def listen(self, handler):
        url = f"{self.base}/agents/{self.pid}/stream"
        while True:
            try:
                log.info("Connecting to prompt stream...")
                async with httpx.AsyncClient(timeout=None) as c:
                    async with c.stream("GET", url, headers=self._h()) as r:
                        r.raise_for_status()
                        log.info("Stream connected")
                        async for line in r.aiter_lines():
                            if line.startswith("data:"):
                                try:
                                    asyncio.create_task(handler(json.loads(line[5:].strip())))
                                except Exception:
                                    pass
            except Exception as e:
                log.warning(f"Stream disconnected: {e}. Retry in 5s...")
                await asyncio.sleep(5)


class AgentWatcher(FileSystemEventHandler):
    def __init__(self, cfg, cb):
        self.ignore = cfg.get("watch", {}).get("ignore", [])
        self.debounce = cfg.get("watch", {}).get("debounce_ms", 800) / 1000
        self.cb = cb
        self._pending = {}
        self._loop = None

    def set_loop(self, loop): self._loop = loop

    def _skip(self, path):
        for p in self.ignore:
            if fnmatch.fnmatch(path, p) or p.rstrip("/") in path:
                return True
        for part in Path(path).parts:
            if part.startswith(".") or part in ("__pycache__", "node_modules"):
                return True
        return False

    def _fire(self, path, etype):
        if self._skip(path) or not self._loop: return
        if path in self._pending: self._pending[path].cancel()
        def run():
            asyncio.run_coroutine_threadsafe(self.cb(path, etype), self._loop)
        self._pending[path] = self._loop.call_later(self.debounce, run)

    def on_modified(self, e):
        if not e.is_directory: self._fire(e.src_path, "modified")
    def on_created(self, e):
        if not e.is_directory: self._fire(e.src_path, "created")
    def on_deleted(self, e):
        if not e.is_directory: self._fire(e.src_path, "deleted")
    def on_moved(self, e):
        self._fire(e.dest_path, "moved")


class Agent:
    def __init__(self):
        self.cfg = load_config()
        self.pid = self.cfg["agent"]["id"]
        self.q = LocalQueue()
        self.orch = OrchestratorClient(self.cfg, self.q)
        self.llm = LLMClient(self.cfg)
        self.applier = FileApplier(self.cfg.get("permissions", {}).get("protected_paths", []))

    async def on_file(self, path, etype):
        log.info(f"File {etype}: {path}")
        await self.orch.send({
            "type": "file_changed", "project": self.pid,
            "event_type": etype, "path": path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    DEPLOY_EXCLUDE_DIRS = {
        "node_modules", ".git", "__pycache__", ".next", "dist", "build",
        "venv", ".venv", "vendor", ".cache", "data", "storage",
        ".nuxt", ".output", ".turbo",
    }
    DEPLOY_EXCLUDE_FILES = {
        "agent.log", "agent_queue.json", ".env.agent",
    }
    DEPLOY_MAX_SIZE = 50 * 1024 * 1024  # 50MB

    def package_project(self) -> str:
        """Package project files into tar.gz, respecting exclude patterns."""
        deploy_cfg = self.cfg.get("deploy", {})
        extra_exclude = deploy_cfg.get("exclude", [])
        root = Path(".")
        tarball = tempfile.mktemp(suffix=".tar.gz", prefix=f"deploy-{self.pid}-")

        with tarfile.open(tarball, "w:gz") as tf:
            for dirpath, dirnames, filenames in os.walk(root):
                # Filter out excluded directories in-place
                dirnames[:] = [
                    d for d in dirnames
                    if d not in self.DEPLOY_EXCLUDE_DIRS
                    and not d.startswith(".")
                ]
                for fname in filenames:
                    if fname in self.DEPLOY_EXCLUDE_FILES:
                        continue
                    if any(fname.endswith(".bak." + ext) for ext in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]):
                        continue
                    filepath = Path(dirpath) / fname
                    rel = filepath.relative_to(root)
                    # Check extra excludes (glob patterns)
                    if any(fnmatch.fnmatch(str(rel), pat) for pat in extra_exclude):
                        continue
                    try:
                        tf.add(str(filepath), arcname=str(rel))
                    except (PermissionError, OSError) as e:
                        log.warning(f"Skip {rel}: {e}")

        size = Path(tarball).stat().st_size
        if size > self.DEPLOY_MAX_SIZE:
            Path(tarball).unlink()
            raise RuntimeError(f"Package too large: {size} bytes (max {self.DEPLOY_MAX_SIZE})")
        log.info(f"Packaged project: {size} bytes → {tarball}")
        return tarball

    async def on_deploy(self, data):
        """Handle deploy command: package project and upload to orchestrator."""
        tid = data.get("task_id")
        log.info(f"Deploy [task={tid}]")
        await self.orch.update_task(tid, "running", {"status": "packaging"})

        # Check permission
        if not self.cfg.get("permissions", {}).get("can_deploy", False):
            log.error("Deploy blocked: can_deploy is false in permissions")
            await self.orch.update_task(tid, "failed", {"error": "Deploy not permitted (can_deploy: false)"})
            return

        # Read deploy config
        deploy_cfg = self.cfg.get("deploy", {})
        if not deploy_cfg.get("domain"):
            await self.orch.update_task(tid, "failed", {"error": "No deploy.domain in .agent.yaml"})
            return

        tarball = None
        try:
            # Package
            tarball = self.package_project()
            await self.orch.update_task(tid, "running", {"status": "uploading"})

            # Upload
            result = await self.orch.upload_deploy(tarball, deploy_cfg)
            await self.orch.update_task(tid, "done", {
                "status": "uploaded",
                "deployment_id": result.get("deployment_id"),
                "message": f"Uploaded to server. Deployment in progress.",
            })
            log.info(f"Deploy task {tid} uploaded. Server deploying...")

        except Exception as e:
            log.error(f"Deploy task {tid} failed: {e}", exc_info=True)
            await self.orch.update_task(tid, "failed", {"error": str(e)})
        finally:
            if tarball and Path(tarball).exists():
                Path(tarball).unlink(missing_ok=True)

    async def on_prompt(self, data):
        # Check if this is a deploy command
        if data.get("type") == "deploy" or data.get("deploy_after"):
            return await self.on_deploy(data)

        tid = data.get("task_id")
        prompt = data.get("prompt", "")
        files = data.get("context_files", [])
        log.info(f"Prompt [task={tid}]: {prompt[:60]}...")
        await self.orch.update_task(tid, "running", {})
        try:
            response, llm_meta = await self.llm.complete(prompt, files, cfg=self.cfg)
            results = []
            if self.cfg.get("permissions", {}).get("can_edit_files", True):
                results = self.applier.apply(response)
            result = {
                "preview": response[:300],
                "written": [r for r in results if r["status"] == "written"],
                "blocked": [r for r in results if r["status"] == "blocked"],
                "errors": [r for r in results if r["status"] == "error"],
            }
            await self.orch.update_task(tid, "done", result)
            log.info(f"Task {tid} done. Written: {len(result['written'])}")

            # Log training data
            try:
                await self.orch.log_training(
                    system_prompt=llm_meta.get("system_prompt", ""),
                    user_input=llm_meta.get("user_input", ""),
                    assistant_output=response,
                    task_id=tid,
                    model=f"{llm_meta.get('provider', '')}/{llm_meta.get('model', '')}",
                    project=self.pid,
                    files_written=len(result["written"]),
                    success=True,
                    tokens_in=llm_meta.get("tokens_in", 0),
                    tokens_out=llm_meta.get("tokens_out", 0),
                )
            except Exception as te:
                log.warning(f"Training data log failed: {te}")
        except Exception as e:
            log.error(f"Task {tid} failed: {e}", exc_info=True)
            await self.orch.update_task(tid, "failed", {"error": str(e)})

    async def run(self):
        log.info(f"Starting: {self.pid}")
        await self.orch.register(self.cfg)
        await self.orch.send({
            "type": "agent_started", "project": self.pid,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "queue_backlog": self.q.size(),
        })

        paths = self.cfg.get("watch", {}).get("paths", ["."])
        watcher = AgentWatcher(self.cfg, self.on_file)
        loop = asyncio.get_event_loop()
        watcher.set_loop(loop)

        observer = Observer()
        for p in paths:
            if Path(p).exists():
                observer.schedule(watcher, str(p), recursive=True)
                log.info(f"Watching: {Path(p).resolve()}")
            else:
                log.warning(f"Path not found: {p}")
        observer.start()

        try:
            await self.orch.listen(self.on_prompt)
        finally:
            observer.stop()
            observer.join()


if __name__ == "__main__":
    asyncio.run(Agent().run())
