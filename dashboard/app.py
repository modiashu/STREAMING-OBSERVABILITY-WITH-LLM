"""
Observability Dashboard
Real-time visualization of metrics, anomalies, and incident summaries
"""

import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

# Page configuration
st.set_page_config(
    page_title="Streaming Observability Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database connection
DB_PATH = os.getenv('DUCKDB_PATH', '/data/observability.db')

def get_connection():
    """Get database connection (short-lived to avoid blocking writes)"""
    return duckdb.connect(DB_PATH, read_only=True)

def fetch_metrics(conn, hours=1):
    """Fetch metrics for the last N hours"""

    query = f"""
        SELECT 
            window_start,
            window_end,
            service,
            request_count,
            error_count,
            error_rate,
            avg_latency_ms,
            p95_latency_ms,
            p99_latency_ms
        FROM service_metrics
        WHERE window_start >= NOW() - INTERVAL '{hours} hours'
        ORDER BY window_start DESC
    """
    return conn.execute(query).df()

def fetch_anomalies(conn, hours=24):
    """Fetch anomalies for the last N hours"""

    query = f"""
        SELECT 
            id,
            detected_at,
            window_start,
            window_end,
            service,
            anomaly_type,
            severity,
            metric_name,
            metric_value,
            baseline_value,
            threshold_value,
            description,
            resolved
        FROM anomalies
        WHERE detected_at >= NOW() - INTERVAL '{hours} hours'
        ORDER BY detected_at DESC
    """
    return conn.execute(query).df()

def fetch_incident_summaries(conn, hours=24):
    """Fetch incident summaries for the last N hours"""
    query = f"""
        SELECT 
            i.id,
            i.created_at,
            i.service,
            i.time_window_start,
            i.time_window_end,
            i.summary,
            i.possible_causes,
            i.affected_metrics,
            i.llm_model,
            a.severity,
            a.anomaly_type
        FROM incident_summaries i
        JOIN anomalies a ON i.anomaly_id = a.id

        WHERE i.created_at >= NOW() - INTERVAL '{hours} hours'
        ORDER BY i.created_at DESC
    """
    return conn.execute(query).df()

def plot_request_rate(df):
    """Plot request rate over time"""
    fig = px.line(
        df,
        x='window_start',
        y='request_count',
        color='service',
        title='Request Rate by Service',
        labels={'window_start': 'Time', 'request_count': 'Requests/min'}
    )
    fig.update_layout(hovermode='x unified')
    return fig

def plot_error_rate(df):
    """Plot error rate over time"""

    fig = px.line(
        df,
        x='window_start',
        y='error_rate',
        color='service',
        title='Error Rate by Service',
        labels={'window_start': 'Time', 'error_rate': 'Error Rate'}
    )
    fig.update_yaxes(tickformat='.1%')
    fig.update_layout(hovermode='x unified')
    return fig

def plot_latency(df):
    """Plot latency metrics over time"""
    fig = go.Figure()
    
    for service in df['service'].unique():
        service_df = df[df['service'] == service]
        
        # P50 (avg)
        fig.add_trace(go.Scatter(
            x=service_df['window_start'],
            y=service_df['avg_latency_ms'],
            name=f'{service} - Avg',
            mode='lines',
            line=dict(width=2)
        ))
        
        # P95
        fig.add_trace(go.Scatter(
            x=service_df['window_start'],
            y=service_df['p95_latency_ms'],
            name=f'{service} - P95',
            mode='lines',
            line=dict(width=1, dash='dash')
        ))
    
    fig.update_layout(
        title='Latency by Service',
        xaxis_title='Time',
        yaxis_title='Latency (ms)',
        hovermode='x unified'
    )
    
    return fig

def plot_anomaly_timeline(anomalies_df):
    """Plot anomaly timeline"""
    if anomalies_df.empty:
        return None
    
    # Map severity to numeric values for sizing
    severity_map = {'low': 10, 'medium': 20, 'high': 30, 'critical': 40}
    anomalies_df['severity_size'] = anomalies_df['severity'].map(severity_map)
    
    # Map severity to colors
    color_map = {
        'low': 'blue',
        'medium': 'yellow',
        'high': 'orange',
        'critical': 'red'
    }
    anomalies_df['color'] = anomalies_df['severity'].map(color_map)
    
    fig = px.scatter(
        anomalies_df,
        x='detected_at',
        y='service',
        color='severity',
        size='severity_size',
        hover_data=['anomaly_type', 'description'],
        title='Anomaly Timeline',
        labels={'detected_at': 'Detection Time', 'service': 'Service'},
        color_discrete_map=color_map
    )
    
    fig.update_layout(showlegend=True)
    
    return fig

def main():
    """Main dashboard function"""
    st.title("📊 Streaming Observability Dashboard")
    st.markdown("Real-time monitoring of service telemetry, anomalies, and incidents")
    
    # Sidebar
    st.sidebar.header("Configuration")
    
    time_window = st.sidebar.selectbox(
        "Time Window",
        options=[1, 3, 6, 12, 24],
        format_func=lambda x: f"Last {x} hour{'s' if x > 1 else ''}",
        index=1  # Default to 3 hours
    )
    
    auto_refresh = st.sidebar.checkbox("Auto Refresh (30s)", value=True)
    
    if auto_refresh:
        st.sidebar.info("Dashboard refreshes every 30 seconds")
    
    # Get connection
    try:
        conn = get_connection()
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        st.stop()
    
    # Fetch data
    with st.spinner("Loading data..."):
        metrics_df = fetch_metrics(conn, hours=time_window)
        anomalies_df = fetch_anomalies(conn, hours=time_window)
        summaries_df = fetch_incident_summaries(conn, hours=time_window)

    # Close connection immediately to avoid blocking writes
    conn.close()
    
    # Summary metrics
    st.header("📈 Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_requests = metrics_df['request_count'].sum() if not metrics_df.empty else 0
        st.metric("Total Requests", f"{total_requests:,}")
    
    with col2:
        avg_error_rate = metrics_df['error_rate'].mean() if not metrics_df.empty else 0
        st.metric("Avg Error Rate", f"{avg_error_rate:.2%}")
    
    with col3:
        total_anomalies = len(anomalies_df) if not anomalies_df.empty else 0
        st.metric("Anomalies Detected", total_anomalies)
    
    with col4:
        active_anomalies = len(anomalies_df[~anomalies_df['resolved']]) if not anomalies_df.empty else 0
        st.metric("Active Anomalies", active_anomalies)
    
    # Metrics visualization
    st.header("📊 Service Metrics")
    
    if not metrics_df.empty:
        tab1, tab2, tab3 = st.tabs(["Request Rate", "Error Rate", "Latency"])
        
        with tab1:
            st.plotly_chart(plot_request_rate(metrics_df), use_container_width=True)
        
        with tab2:
            st.plotly_chart(plot_error_rate(metrics_df), use_container_width=True)
        
        with tab3:
            st.plotly_chart(plot_latency(metrics_df), use_container_width=True)
    else:
        st.info("No metrics data available for the selected time window.")
    
    # Anomalies section
    st.header("🚨 Anomalies")
    
    if not anomalies_df.empty:
        # Timeline
        timeline_fig = plot_anomaly_timeline(anomalies_df)
        if timeline_fig:
            st.plotly_chart(timeline_fig, use_container_width=True)
        
        # Anomalies table
        st.subheader("Recent Anomalies")
        
        # Format for display
        display_df = anomalies_df[[
            'detected_at', 'service', 'anomaly_type', 'severity', 
            'description', 'resolved'
        ]].copy()
        
        display_df['detected_at'] = pd.to_datetime(display_df['detected_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Color code by severity
        def highlight_severity(row):
            if row['severity'] == 'critical':
                return ['background-color: #ffcccc'] * len(row)
            elif row['severity'] == 'high':
                return ['background-color: #ffe6cc'] * len(row)
            elif row['severity'] == 'medium':
                return ['background-color: #ffffcc'] * len(row)
            return [''] * len(row)
        
        st.dataframe(
            display_df.style.apply(highlight_severity, axis=1),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("No anomalies detected in the selected time window.")
    
    # Incident summaries
    st.header("📝 Incident Summaries (LLM-Generated)")
    
    if not summaries_df.empty:
        for _, summary in summaries_df.iterrows():
            severity_emoji = {
                'low': '🟢',
                'medium': '🟡',
                'high': '🟠',
                'critical': '🔴'
            }.get(summary['severity'], '⚪')
            
            with st.expander(
                f"{severity_emoji} {summary['service']} - {summary['anomaly_type']} "
                f"({summary['created_at'].strftime('%Y-%m-%d %H:%M')})"
            ):
                st.markdown(f"**Time Window:** {summary['time_window_start']} to {summary['time_window_end']}")
                st.markdown(f"**Severity:** {summary['severity'].upper()}")
                st.markdown(f"**Affected Metrics:** {summary['affected_metrics']}")
                
                st.markdown("### Summary")
                st.write(summary['summary'])
                
                st.markdown("### Possible Causes")
                st.write(summary['possible_causes'])
                
                st.caption(f"Generated by: {summary['llm_model']}")
    else:
        st.info("No incident summaries available.")
    
    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Auto-refresh
    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()

if __name__ == '__main__':
    main()
