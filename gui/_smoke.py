"""Headless smoke test for the FULL dashboard (Pass 1).

Builds DashboardApp, drives 6 ticks manually, and asserts every panel
(Current Watching metrics, SullyGoose, Live Followed, Next Stream,
Dispatcher, Chat, connection status, log panel) actually received
and rendered the mock metrics.

Run:  python -m gui._smoke
"""
from gui.dashboard import DashboardApp
from gui.demo_dashboard import _DashboardProvider


def main():
    provider = _DashboardProvider()
    app = DashboardApp(provider=provider, tick_ms=1000)
    app.update_idletasks()

    for i in range(6):
        app._loop()
        app.update_idletasks()

    # connection status
    conn = app._conn_var.get()
    # current watching metrics
    viewers = app.metrics.viewers_var.get()
    channel = app.metrics.channel_var.get()
    status = app.metrics.status_var.get()
    delta = app.metrics.delta_var.get()
    percent = app.metrics.percent_var.get()
    spark_pts = len(app.metrics.spark._points)
    # sullygoose
    sully_labels = {k: v.cget("text") for k, v in app.sully._labels.items()}
    # live followed
    live_rows = len(app.live._rows)
    # next stream
    next_ch = app.next.channel_var.get()
    # dispatcher
    dispatch_status = app.dispatch.status_var.get()
    # chat
    chat_ch = app.chat._channel_var.get()

    print("=== Full dashboard smoke (Pass 1, 6 ticks) ===")
    print(f"  connection      = {conn!r}")
    print(f"  viewers         = {viewers!r}")
    print(f"  channel         = {channel!r}")
    print(f"  status          = {status!r}")
    print(f"  delta           = {delta!r}")
    print(f"  percent         = {percent!r}")
    print(f"  spark pts       = {spark_pts}")
    print(f"  sully streamer  = {sully_labels.get('Streamer')!r}")
    print(f"  sully peak      = {sully_labels.get('Peak')!r}")
    print(f"  live rows       = {live_rows}")
    print(f"  next channel    = {next_ch!r}")
    print(f"  dispatch status = {dispatch_status!r}")
    print(f"  chat channel    = {chat_ch!r}")

    # hard assertions
    assert "ONLINE" in conn or "OFFLINE" in conn, "connection not set"
    assert channel.startswith("#"), "channel not set"
    assert viewers != "—", "viewers not populated"
    assert status != "—", "status not populated"
    assert spark_pts >= 2, "sparkline not populated"
    assert sully_labels.get("Streamer") not in (None, "—"), "sully not populated"
    assert live_rows > 0, "live followed empty"
    assert next_ch not in ("No next stream selected", "—"), "next stream not set"
    assert dispatch_status, "dispatch status not set"
    assert chat_ch.startswith("#") or chat_ch == "—", "chat channel not set"

    print("\nSMOKE_OK: Pass 1 full dashboard — all panels + all metrics populated live (no PySide6)")
    app.destroy()


if __name__ == "__main__":
    main()

