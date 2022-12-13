import json
import plotly
import dash
import os
import pandas as pd
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_snapshots
import dash_design_kit as ddk
import dashboard_engine as dbe
from dash import Input, Output, State, callback, dcc, html, ctx
from sqlalchemy.engine import create_engine
from dotenv import load_dotenv

from assets.theme import theme
import utils.chart_utils as figs

# ------------- CONFIG AND GLOBAL VARIABLES

load_dotenv()

SERVER_HOSTNAME = os.getenv("SERVER_HOSTNAME")
HTTP_PATH = os.getenv("HTTP_PATH")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

os.environ["SNAPSHOT_DATABASE_URL"] = (
    os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:docker@127.0.0.1:5432",
    )
    if os.name == "nt"
    else os.environ.get(
        "DATABASE_URL",
        "sqlite:///snapshot-dev.db",
    )
)

engine = create_engine(
    f"databricks+connector://token:{ACCESS_TOKEN}@{SERVER_HOSTNAME}:443/plotly_iot_dashboard",
    connect_args={"http_path": f"{HTTP_PATH}"},
)

stmt = f"SELECT * FROM plotly_iot_dashboard_new.bronze_sensors ORDER BY timestamp ASC LIMIT 1000;"
df = pd.read_sql_query(stmt, engine)

dfs = {"IoT Sensor Data": df}

app = dash.Dash(__name__, suppress_callback_exceptions=True)

app.title = "Make Dash Apps with Databricks"
server = app.server
conn_provider = dbe.MultiPandasConnectionProvider(dfs)
dbengine = dbe.DashboardEngine(app, conn_provider)
snap = dash_snapshots.DashSnapshots(app)

# ------------- LAYOUT

app.layout = ddk.App(
    children=[
        ddk.Header(
            children=[
                ddk.Logo(
                    src=dash.get_asset_url("images/plotly-logo-dark-theme.png"),
                    className="header-logos-left",
                ),
                ddk.Title(app.title),
                ddk.Menu(
                    [
                        dcc.Link("Stream", href=app.get_relative_path("/realtime")),
                        dcc.Link(
                            "New Dashboard", href=app.get_relative_path("/create")
                        ),
                        dcc.Link("Archive", href=app.get_relative_path("/archive")),
                    ]
                ),
            ]
        ),
        dcc.Location(id="url"),
        html.Div(id="content"),
    ],
    theme=theme
)


def realtime_page():
    return html.Div(
        [
            ddk.Row(
                [
                    ddk.ControlCard(
                        [
                            ddk.ControlItem(
                                dcc.Dropdown(
                                    id="select",
                                    options=[
                                        {
                                            "label": "Number of steps",
                                            "value": "NumSteps",
                                        },
                                        # {"label": 'Miles Walked', "value": 'Miles'},
                                        {"label": "Calories", "value": "CaloriesBurnt"},
                                    ],
                                    value="NumSteps",
                                ),
                                label="Choose What to Stream",
                            )
                        ],
                        width=50,
                    ),
                    ddk.Block(
                        [
                            ddk.Block(
                                [
                                    ddk.DataCard(
                                        id="update-frequency",
                                        label="Data update frequency",
                                        value="5 seconds",
                                        width=50,
                                    ),
                                    ddk.DataCard(
                                        id="last-updated",
                                        label="Latest timestamp",
                                        width=50,
                                    ),
                                ],
                                width=100,
                            ),
                            ddk.Block(
                                [
                                    html.Button(
                                        id="sync-update-frequency",
                                        children="Sync Updates with Stream Frequency",
                                        style={
                                            "marginLeft": "15px",
                                            "width": "calc(100% - 30px",
                                        },
                                    )
                                ],
                                width=100,
                            ),
                        ],
                        width=50,
                    ),
                ]
            ),
            ddk.Card(
                children=[
                    ddk.Graph(
                        id="graph",
                        className="glow",
                        config={"displayModeBar": False},
                        animate=False,
                        style={"height": "calc(100vh - 285px"},
                    ),
                    dcc.Interval(id="live-data-interval", interval=5000, n_intervals=0),
                ]
            ),
        ]
    )


def archive_page():
    keys = dash_snapshots.constants.KEYS
    return html.Div(
        [
            ddk.Card(
                children=[
                    ddk.CardHeader(title=""),
                    snap.ArchiveTable(
                        columns=[
                            {"id": keys["snapshot_id"], "name": "Link"},
                            {"id": "title", "name": "Title"},
                            {"id": keys["username"], "name": "Created By"},
                            {"id": keys["created_time"], "name": "Created On"},
                        ],
                        version=1,
                    ),
                ]
            ),
        ]
    )


def dashboard_page(snapshot_id, show_mode):
    if snapshot_id:
        new = False
        dashboard = snap.snapshot_get(snapshot_id)
        title = snap.meta_get(snapshot_id, "title", "")

    else:
        snapshot_id = ""
        new = True
        title = ""
        dashboard = dict(
            connection_params=list(dfs.keys())[0],
            elements=[],
            arrangement=None,
        )

    state, canvas = dbengine.make_state_and_canvas(
        dashboard_id="db",
        elements=dashboard["elements"],
        arrangement=dashboard["arrangement"],
        connection_params=dashboard["connection_params"],
        editable=not show_mode,
    )

    hide = dict(display="none")

    menu_items = [
        html.Button("Save", id="save", style=hide if show_mode else None),
        html.Button("Save a Copy", id="fork", style=hide if new or show_mode else None),
        html.Button("Delete", id="delete", style=hide if new or show_mode else None),
        dcc.Link(
            "Edit",
            href=snap.relpath("/" + snapshot_id + "/edit"),
            style=None if show_mode else hide,
        ),
        dcc.Link("Back to Archive", href=snap.relpath("/archive")),
    ]

    return html.Div(
        [
            ddk.Header(
                children=[
                    ddk.Menu(menu_items),
                ]
            ),
            ddk.ControlCard(
                orientation="horizontal",
                style=hide if show_mode else None,
                children=[
                    ddk.ControlItem(
                        dcc.Input(id="dashboard-title", value=title, type="text"),
                        label="Title",
                        className="glow",
                    ),
                    ddk.ControlItem(
                        dcc.Dropdown(
                            id="dashboard-connstr",
                            value=dashboard["connection_params"],
                            disabled=(not new),
                            className="glow",
                            options=[
                                {"label": x, "value": x} for x in list(dfs.keys())
                            ],
                        ),
                        label="Dataset",
                    ),
                ],
            ),
            html.Div(id="snapshot_id", children=snapshot_id, style=hide),
            html.Div(id="state_and_canvas", children=[state, canvas]),
        ]
    )


# ------------- CALLBACKS


@callback(
    Output("live-data-interval", "interval"),
    Output("update-frequency", "value"),
    Input("sync-update-frequency", "n_clicks"),
    prevent_initial_call=True,
)
def update_interval(n_clicks):
    stmt_react = f"""
    WITH log AS (DESCRIBE HISTORY real_time_iot_dashboard.bronze_sensors), 
    state AS (SELECT version, timestamp, operation FROM log WHERE (timestamp >= current_timestamp()
     - INTERVAL '24 hours') AND operation IN ('MERGE', 'WRITE', 'DELETE', 'STREAMING UPDATE') ORDER 
     By version DESC), comparison AS (SELECT DISTINCT s1.version, s1.timestamp, s1.operation, LAG(version) 
     OVER (ORDER BY version) AS Previous_Version, LAG(timestamp) OVER (ORDER BY timestamp) AS 
     Previous_Timestamp FROM state AS s1 ORDER BY version DESC) SELECT date_trunc('hour', timestamp) AS HourBlock, 
     AVG(timestamp::double - Previous_Timestamp::double) AS AvgUpdateFrequencyInSeconds FROM comparison GROUP BY 
     date_trunc('hour', timestamp) ORDER BY HourBlock;
     """
    if not n_clicks:
        return dash.no_update
    df_describe = pd.read_sql_query(stmt_react, engine)
    update_time = int(df_describe["AvgUpdateFrequencyInSeconds"].iloc[-1])
    print(f"Updating trigger interval to {update_time}")
    return update_time * 1000, f"{update_time} seconds"


@callback(
    Output("last-updated", "value"),
    Output("graph", "figure"),
    Input("live-data-interval", "n_intervals"),
    Input("select", "value"),
)
def update_data(n, column):
    stmt_gold = f"SELECT Smoothed{column}30SecondMA, Smoothed{column}120SecondMA, timestamp FROM real_time_iot_dashboard.gold_sensors_stateful LIMIT 100"
    df_gold = pd.read_sql_query(stmt_gold, engine)
    figure = figs.fig_live(df_gold, column)
    new_timestamp = df_gold["timestamp"].iloc[0].strftime("%H:%M:%S")
    print(f"Updating chart with {column}, last timestamp {new_timestamp}")
    return new_timestamp, figure


@callback(
    Output("url", "href"),
    Input("save", "n_clicks"),
    Input("fork", "n_clicks"),
    Input("delete", "n_clicks"),
    State(dbengine.state_id("db"), "elements"),
    State(dbengine.canvas_id("db"), "arrangement"),
    State("snapshot_id", "children"),
    State("dashboard-title", "value"),
    State("dashboard-connstr", "value"),
)
def lifecycle(
    n_save_clicks,
    n_fork_clicks,
    n_delete_clicks,
    elements,
    arrangement,
    snapshot_id,
    title,
    connection_params,
):
    trigger = ctx.triggered_id
    dashboard = dict(
        connection_params=connection_params,
        elements=elements,
        arrangement=arrangement,
    )
    print(f"{trigger} action triggered for Dashboard Engine view")
    if trigger == "save" and n_save_clicks:
        if not snapshot_id:
            snapshot_id = snap.snapshot_save(dashboard)
        else:  # overwrite
            blob = json.dumps(dashboard, cls=plotly.utils.PlotlyJSONEncoder)
            snap.save_blob(snapshot_id, "layout-json", blob)
    elif trigger == "fork" and n_fork_clicks:
        snapshot_id = snap.snapshot_save(dashboard)
    elif trigger == "delete" and n_delete_clicks:
        snap.snapshot_delete(snapshot_id)
        return snap.relpath("/")
    else:
        raise PreventUpdate

    snap.meta_update(snapshot_id, {"title": title})
    return snap.relpath("/" + snapshot_id)


@callback(
    Output("state_and_canvas", "children"),
    Input("dashboard-connstr", "value"),
    prevent_initial_call=True,
)
def change_dataset(connection_params):
    return dbengine.make_state_and_canvas(
        dashboard_id="db", connection_params=connection_params
    )


@callback(Output("content", "children"), [Input("url", "pathname")])
def router(pathname):
    if pathname is None or pathname in app.get_relative_path("/realtime"):
        return realtime_page()
    if pathname in app.get_relative_path("/create/"):
        return dashboard_page(None, False)
    if pathname in app.get_relative_path("/archive"):
        return archive_page()
    if pathname.startswith(snap.relpath("/snapshot-")):
        snapshot_id = pathname.replace(snap.relpath("/"), "", 1).replace("/edit", "")
        return dashboard_page(snapshot_id, not pathname.endswith("/edit"))
    return "404"


if __name__ == "__main__":
    app.run_server(debug=True, port=8051)
