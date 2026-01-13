import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

# -----------------------
# CONFIG
# -----------------------
DB_PATH = Path("scans.db")  # adjust if needed


# -----------------------
# DB HELPERS
# -----------------------
@st.cache_resource
def get_connection(db_path: Path):
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")
    conn = sqlite3.connect(db_path)
    # Return connection; Streamlit will keep it cached
    return conn


@st.cache_data
def load_table(table_name: str) -> pd.DataFrame:
    conn = get_connection(DB_PATH)
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    return df


def prepare_data():
    items = load_table("items")
    events = load_table("events")
    staffs = load_table("staffs")
    trays = load_table("trays")
    tray_items = load_table("tray_items")

    # Parse datetimes
    for df, col in [(items, "created_at"),
                    (events, "created_at"),
                    (staffs, "created_at"),
                    (trays, "created_at"),
                    (tray_items, "bound_at")]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Also parse ts_local for events if you prefer to use local time
    if "ts_local" in events.columns:
        events["ts_local_dt"] = pd.to_datetime(events["ts_local"], errors="coerce")
    else:
        events["ts_local_dt"] = events["created_at"]

    # Rename to avoid collision
    if "division" in events.columns:
        events = events.rename(columns={"division": "event_division"})
    if "division" in staffs.columns:
        staffs = staffs.rename(columns={"division": "staff_division"})

    # Merge staff info into events (left join on phone)
    events = events.merge(
        staffs[["phone", "name", "staff_division"]],
        how="left",
        left_on="from_number",
        right_on="phone",
    )

    # Convenience cols
    events["event_date"] = events["ts_local_dt"].dt.date

    return items, events, staffs, trays, tray_items


# -----------------------
# MAIN APP
# -----------------------
def main():
    st.set_page_config(
        page_title="MBG Kitchen – WhatsApp Ops Dashboard",
        layout="wide",
    )

    st.title("📊 MBG Kitchen – WhatsApp Ops Dashboard")

    # Load data
    try:
        items, events, staffs, trays, tray_items = prepare_data()
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    # -------------------
    # Sidebar filters
    # -------------------
    st.sidebar.header("Filters")

    if not events.empty:
        min_date = events["event_date"].min()
        max_date = events["event_date"].max()
    else:
        min_date = max_date = None

    date_range = st.sidebar.date_input(
        "Event date range",
        value=(min_date, max_date) if min_date and max_date else [],
        help="Filter events by date (based on ts_local).",
    )

    # Division filter
    divisions = sorted(
        set(events["event_division"].dropna().unique().tolist())
    )
    selected_divisions = st.sidebar.multiselect(
        "Division (from events)",
        options=divisions,
        default=divisions,
    )

    # Staff filter by name/phone
    staff_options = (
        staffs.assign(label=lambda df: df["name"] + " (" + df["phone"].astype(str) + ")")
        if not staffs.empty
        else pd.DataFrame(columns=["phone", "label"])
    )

    selected_staff_labels = st.sidebar.multiselect(
        "Staff",
        options=staff_options["label"].tolist(),
        default=staff_options["label"].tolist(),
    )

    # Map labels back to phones
    selected_staff_phones = (
        staff_options[staff_options["label"].isin(selected_staff_labels)]["phone"]
        .astype(str)
        .tolist()
        if not staff_options.empty
        else []
    )

    # Apply filters to events
    events_filtered = events.copy()

    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range
        if start_date and end_date:
            events_filtered = events_filtered[
                (events_filtered["event_date"] >= start_date)
                & (events_filtered["event_date"] <= end_date)
            ]

    if selected_divisions:
        events_filtered = events_filtered[
            events_filtered["event_division"].isin(selected_divisions)
        ]

    if selected_staff_phones:
        events_filtered = events_filtered[
            events_filtered["from_number"].astype(str).isin(selected_staff_phones)
        ]

    # -------------------
    # Overview metrics
    # -------------------
    st.subheader("Overview")

    col1, col2, col3, col4 = st.columns(4)

    total_items = len(items)
    total_events = len(events)
    total_staffs = len(staffs)
    total_trays = len(trays)

    with col1:
        st.metric("Total Items", total_items)
    with col2:
        st.metric("Total Events", total_events)
    with col3:
        st.metric("Total Staff", total_staffs)
    with col4:
        st.metric("Total Trays", total_trays)

    # Date range display
    if not events.empty:
        st.caption(
            f"Events from **{events['event_date'].min()}** "
            f"to **{events['event_date'].max()}** "
            f"(based on local timestamps)."
        )

    # -------------------
    # Charts section
    # -------------------
    st.subheader("Activity Charts (Filtered)")

    chart_col1, chart_col2 = st.columns(2)

    # Events per day
    if not events_filtered.empty:
        events_per_day = (
            events_filtered.groupby("event_date")["id"]
            .count()
            .rename("events")
            .reset_index()
        )
        with chart_col1:
            st.markdown("**Events per Day**")
            st.line_chart(
                events_per_day.set_index("event_date")["events"]
            )
    else:
        with chart_col1:
            st.info("No events for current filter.")

    # Events by division
    if not events_filtered.empty:
        events_by_div = (
            events_filtered.groupby("event_division")["id"]
            .count()
            .rename("events")
            .reset_index()
        )
        with chart_col2:
            st.markdown("**Events by Division**")
            st.bar_chart(
                events_by_div.set_index("event_division")["events"]
            )
    else:
        with chart_col2:
            st.info("No events for current filter.")

    # Items by name (overall)
    st.subheader("Items Summary")
    if not items.empty:
        items_by_name = (
            items.groupby("name")["id"]
            .count()
            .rename("count")
            .reset_index()
            .sort_values("count", ascending=False)
        )
        st.markdown("**Items by Name**")
        st.bar_chart(items_by_name.set_index("name")["count"])
    else:
        st.info("No items in database.")

    st.markdown("---")

    # -------------------
    # Tabs for detailed views
    # -------------------
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📦 Items", "📝 Events Log", "👤 Staff", "🧺 Trays"]
    )

    # Items tab
    with tab1:
        st.markdown("### Items")
        if not items.empty:
            item_name_filter = st.text_input(
                "Search by item name (contains)", value=""
            )
            df_items = items.copy()
            if item_name_filter:
                df_items = df_items[
                    df_items["name"]
                    .astype(str)
                    .str.contains(item_name_filter, case=False, na=False)
                ]
            st.dataframe(df_items, use_container_width=True)
        else:
            st.info("No items in database.")

    # Events tab
    with tab2:
        st.markdown("### Events (Filtered by sidebar)")
        if not events_filtered.empty:
            # Select columns to show
            cols_to_show = [
                "id",
                "ts_local",
                "event_division",
                "from_number",
                "name",
                "subject_type",
                "subject_id",
                "message_text",
                "duration_hms",
                "duration_seconds",
            ]
            cols_to_show = [c for c in cols_to_show if c in events_filtered.columns]
            st.dataframe(events_filtered[cols_to_show], use_container_width=True)
        else:
            st.info("No events for the current filter.")

    # Staff tab
    with tab3:
        st.markdown("### Staff")
        if not staffs.empty:
            st.dataframe(
                staffs.rename(
                    columns={
                        "phone": "phone",
                        "name": "name",
                        "staff_division": "division",
                    }
                ),
                use_container_width=True,
            )
        else:
            st.info("No staff registered.")

    # Trays tab
    with tab4:
        st.markdown("### Trays & Tray Items")
        col_t1, col_t2 = st.columns(2)

        with col_t1:
            st.markdown("**Trays**")
            if not trays.empty:
                st.dataframe(trays, use_container_width=True)
            else:
                st.info("No trays in database yet.")

        with col_t2:
            st.markdown("**Tray Items**")
            if not tray_items.empty:
                st.dataframe(tray_items, use_container_width=True)
            else:
                st.info("No tray_items in database yet.")


if __name__ == "__main__":
    main()
