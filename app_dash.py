import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State 
from dash.exceptions import PreventUpdate 
import pandas as pd
import time
import random 

# ІМПОРТУЄМО НАШІ ФАЙЛИ
import analysis 
import plotting_plotly 

# --- НАЛАШТУВАННЯ ---
FILE_NAME = "Europa_highvoltage.graphml"
NODES_TO_ATTACK = 100 

# --- ЕТАП 1: ЗАВАНТАЖЕННЯ ДАНИХ ---
# Цей етап виконується ОДИН РАЗ при запуску програми.
# ------------------------------------------------
print(f"Завантажую граф '{FILE_NAME}'...")
start_time = time.time()
# G_main робимо глобальною, щоб Callback-и мали до неї доступ
G_main = analysis.load_and_prepare_data(FILE_NAME)
print(f"Граф завантажено. ({time.time() - start_time:.2f} сек)")
print("-" * 30)

# --- ЕТАП 2: ПРОВЕДЕННЯ ВСІХ АНАЛІЗІВ ---
# Виконуємо всі "важкі" розрахунки ОДИН РАЗ при запуску,
# щоб дашборд завантажувався вже з готовими даними.
# ------------------------------------------------
print("Проводжу всі аналізи... (це займе ~2-3 хвилини)")
# 2.1: 'Хаби' та 'Тупики'
full_sorted_degree, vulnerable_nodes_list = analysis.get_degree_analysis(G_main)
top_10_hubs_list = full_sorted_degree[:10] 
top_10_hubs_df = pd.DataFrame(top_10_hubs_list, columns=["ID Вузла", "Кількість ЛЕП"]); top_10_hubs_df.index += 1
top_10_hub_nodes_list = [node[0] for node in top_10_hubs_list]
top_100_hub_ids = [node[0] for node in full_sorted_degree[:NODES_TO_ATTACK]]
SOURCE_NODE_ID = top_100_hub_ids[0] # Джерело за замовчуванням
SINK_NODE_ID = vulnerable_nodes_list[0] # Споживач за замовчуванням
vulnerable_nodes_df = pd.DataFrame(vulnerable_nodes_list, columns=["ID Тупикового Вузла"])
# 2.2: Критичність (незважена)
full_sorted_centrality = analysis.get_centrality_analysis(G_main)
top_10_centrality_df = pd.DataFrame(full_sorted_centrality[:10], columns=["ID Вузла", "Показник"])
# 2.3: Критичність (зважена)
full_sorted_weighted_centrality = analysis.get_weighted_centrality_analysis(G_main)
top_10_weighted_centrality_df = pd.DataFrame(full_sorted_weighted_centrality[:10], columns=["ID Вузла", "Показник"])
# 2.4: Стійкість (Цільова атака)
hub_robustness_df = analysis.calculate_robustness(G_main, top_100_hub_ids)
# 2.5: Стійкість (Випадкова відмова)
random_nodes_list = random.sample(list(G_main.nodes()), NODES_TO_ATTACK) 
rand_robustness_df = analysis.calculate_robustness(G_main, random_nodes_list)
# 2.6: 'Вузькі місця' (Потоки) - Розрахунок за замовчуванням
bottleneck_stats_init, bottleneck_df_init = analysis.get_bottleneck_analysis(G_main, SOURCE_NODE_ID, SINK_NODE_ID)
# 2.7: Спільноти
communities_df, communities_count = analysis.get_communities_analysis(G_main)
# 2.8: АНАЛІЗИ НАПРУГИ
voltage_map_df = analysis.get_voltage_data_for_nodes(G_main)
hubs_composition_df = analysis.get_hubs_voltage_composition(G_main, top_10_hubs_list)
print("\n" + "-" * 30); print("Всі аналізи завершено."); print("-" * 30)

# --- ЕТАП 3: ГЕНЕРАЦІЯ ГРАФІКІВ ---
# Викликаємо функції з plotting_plotly.py
# ------------------------------------------------
print("Генерація інтерактивних графіків:")
print("  ...будую гістограму...")
hist_data_df = analysis.get_histogram_data(G_main)
hist_fig = plotting_plotly.create_histogram_fig(hist_data_df)
print("  ...будую гео-мапу напруги...")
geo_fig = plotting_plotly.create_geo_voltage_map(voltage_map_df) 
print("  ...будую графік стійкості...")
robustness_fig = plotting_plotly.create_robustness_curve_fig(hub_robustness_df, rand_robustness_df, NODES_TO_ATTACK)
print("  ...будую графік складу хабів...")
hubs_composition_fig = plotting_plotly.create_hub_voltage_barchart(hubs_composition_df)
print(" -> Графіки - ГОТОВО"); print("-" * 30)

# --- ЕТАП 4: СТВОРЕННЯ GUI (Dash) ---

# --- Допоміжні функції для GUI ---
TABLE_STYLE = {
    'style_cell': {'padding': '10px', 'backgroundColor': '#2B2B2B', 'color': '#DCE4EE', 'border': '1px solid #565A5F'},
    'style_header': {'backgroundColor': '#343638', 'fontWeight': 'bold', 'border': '1px solid #565A5F'},
    'style_data': {'whiteSpace': 'normal', 'height': 'auto'},
    'style_table': {'overflowX': 'auto'}, 
}
LARGE_TABLE_STYLE = TABLE_STYLE.copy()
LARGE_TABLE_STYLE['style_table'] = {'overflowX': 'auto', 'maxHeight': '400px', 'overflowY': 'auto'}

def format_table(df):
    """
    Форматує DataFrame у DataTable з пагінацією (10 рядків).
    @param df (pd.DataFrame): DataFrame для відображення.
    @return (dash_table.DataTable): Готовий компонент таблиці.
    """
    df_display = df.copy()
    # Округляємо float для чистого вигляду
    for col in df_display.columns:
        if pd.api.types.is_float_dtype(df_display[col]):
            df_display[col] = df_display[col].round(6)
    return dash_table.DataTable(
        data=df_display.to_dict('records'),
        columns=[{'name': i, 'id': i} for i in df_display.columns],
        sort_action="native", # Дозволяємо сортування
        page_size=10,         # Пагінація
        **TABLE_STYLE
    )
    
def format_large_table(df):
    """
    Форматує великий DataFrame у DataTable з прокруткою.
    @param df (pd.DataFrame): DataFrame для відображення (напр., 'Тупики').
    @return (dash_table.DataTable): Готовий компонент таблиці.
    """
    df_display = df.copy()
    return dash_table.DataTable(
        data=df_display.to_dict('records'),
        columns=[{'name': i, 'id': i} for i in df_display.columns],
        sort_action="native",
        fixed_rows={'headers': True}, # "Приклеюємо" заголовок при прокрутці
        **LARGE_TABLE_STYLE
    )

# Ініціалізація додатку Dash
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
app.title = "Система моніторингу енергосистеми"

# --- ЛЕЙАУТ (СТРУКТУРА) ДОДАТКУ ---
app.layout = dbc.Container([
    # Заголовок
    dbc.Row(dbc.Col(html.H1("Система моніторингу енергосистеми (v6.2 - KPI)", className="text-center text-primary mt-4 mb-4"))),
    
    # Невидимий компонент для збереження ID вузла, обраного на мапі
    dcc.Store(id='map-click-store'),
    
    # Контейнер з вкладками
    dbc.Tabs(id="tabs-main", children=[
        
        # --- ВКЛАДКА 1: ОГЛЯД ---
        dbc.Tab(label="📊 Загальний огляд", children=[
            dbc.Row([
                dbc.Col(dbc.Card([dbc.CardHeader("Вузли (Підстанції)"), dbc.CardBody(html.H3(f"{G_main.number_of_nodes()}", className="card-title"))], color="primary", outline=True), width=4),
                dbc.Col(dbc.Card([dbc.CardHeader("Ребра (ЛЕП)"), dbc.CardBody(html.H3(f"{G_main.number_of_edges()}", className="card-title"))], color="primary", outline=True), width=4),
                dbc.Col(dbc.Card([dbc.CardHeader("Зв'язність"), dbc.CardBody(html.H3("Повністю зв'язна", className="card-title"))], color="success", outline=True), width=4),
            ], className="mt-4"),
            dbc.Row(dbc.Col(dcc.Graph(figure=hist_fig), width=12), className="mt-4")
        ]),
        
        # --- ВКЛАДКА 2: КРИТИЧНІСТЬ ---
        dbc.Tab(label="🚨 Аналіз критичності", children=[
            dbc.Row([
                dbc.Col([
                    html.H4("🏆 Топ-10 'Топологічних Мостів' (за кількістю ЛЕП)"),
                    format_table(top_10_centrality_df.reset_index(names="Рейтинг"))
                ], width=6),
                dbc.Col([
                    html.H4("🏆 Топ-10 'Транзитних Мостів' (за кілометражем)"),
                    format_table(top_10_weighted_centrality_df.reset_index(names="Рейтинг"))
                ], width=6),
            ], className="mt-4")
        ]),

        # --- ВКЛАДКА 3: АНАЛІЗ ХАБІВ ---
        dbc.Tab(label="📈 Аналіз Хабів", children=[
            dbc.Row([
                dbc.Col([
                    html.H4("🏆 Топ-10 'Хабів' (за кількістю ЛЕП)"),
                    format_table(top_10_hubs_df.reset_index(names="Рейтинг"))
                ], width=5), 
                dbc.Col([
                    html.H4(f"🔌 Склад 'Хабів' за напругою"),
                    # Загортаємо графік у Div з фіксованою висотою, щоб він не "розповзався"
                    html.Div(dcc.Graph(figure=hubs_composition_fig, style={'height': '100%'}), style={'height': '500px'})
                ], width=7), 
            ], className="mt-4")
        ]),

        # --- ВКЛАДКА 4: АНАЛІЗ СТІЙКОСТІ ---
        dbc.Tab(label="🛡️ Аналіз Стійкості", children=[
            dbc.Row(dbc.Col(html.H4(f"Симуляція видалення {NODES_TO_ATTACK} вузлів"), width=12), className="mt-4"),
            dbc.Row(dbc.Col(dcc.Graph(figure=robustness_fig), width=12), className="mt-2")
        ]),

        # --- ВКЛАДКА 5: АНАЛІЗ СПІЛЬНОТ ---
        dbc.Tab(label="🌍 Аналіз спільнот", children=[
            dbc.Row([
                dbc.Col(html.H4(f"Алгоритм знайшов {communities_count} спільнот (кластерів)"), width=12),
                dbc.Col(html.H5("Топ-15 найбільших спільнот:"), width=12, className="mt-3")
            ], className="mt-4"),
            dbc.Row(dbc.Col(format_table(communities_df), width=8), className="mt-2")
        ]),

        # --- ВКЛАДКА 6: ГЕО-МАПА (НАПРУГА) ---
        dbc.Tab(label="🗺️ Гео-мапа (Напруга)", children=[
            dbc.Row(dbc.Col(dcc.Graph(
                id='geo-map-graph', # ID потрібен для Callback
                figure=geo_fig, 
                style={'height': '75vh'} # 75% висоти екрану
            ), width=12), className="mt-4") 
        ]),

        # --- ВКЛАДКА 7: АНАЛІЗ ПОТОКІВ (ІНТЕРАКТИВНА) ---
        dbc.Tab(label="🚇 Аналіз потоків", children=[
            dbc.Row(dbc.Col(html.H4("Аналіз потоків: 'Вузькі місця' (Min-Cut)"), width=12), className="mt-4"),
            
            # Блок 1: Перемикач для мапи
            dbc.Card(dbc.CardBody([
                html.Label("Режим вибору на мапі:", className="fw-bold"),
                dbc.RadioItems(options=[{'label': '⚡ Задати Джерело', 'value': 'source'}, {'label': '🏠 Задати Споживача', 'value': 'sink'}], value='source', id='flow-radio-select', inline=True, className="mt-2"),
                html.Small("Перейдіть на вкладку 'Гео-мапа (Напруга)' та клікніть на вузол, щоб обрати його.", className="text-muted")
            ]), className="mt-3", color="secondary", outline=True),
            
            # Блок 2: Поля вводу та кнопка
            dbc.Card(dbc.CardBody([
                dbc.Row([
                    dbc.Col([html.Label("⚡ ID Вузла-Джерела:", htmlFor="input-source"), dbc.Input(id="input-source", value=SOURCE_NODE_ID, type="text")], width=5),
                    dbc.Col([html.Label("🏠 ID Вузла-Споживача:", htmlFor="input-sink"), dbc.Input(id="input-sink", value=SINK_NODE_ID, type="text")], width=5),
                    dbc.Col([html.Label(" "), dbc.Button("Розрахувати 'Вузьке місце'", id="button-calculate-flow", color="primary", className="w-100")], width=2, className="d-flex align-items-end")
                ]),
                # Тут з'являтимуться повідомлення про помилки
                html.Div(id="output-flow-error", className="mt-3") 
            ]), className="mt-3"),
            
            # Блок 3: Результати (KPI та Таблиця)
            # KPI-картки
            dbc.Row([
                dbc.Col(dbc.Card([dbc.CardHeader("Кількість ЛЕП у розрізі"), dbc.CardBody(html.H3(id="kpi-line-count", children=f"{bottleneck_stats_init['line_count']}"))], color="danger", outline=True), width=4),
                dbc.Col(dbc.Card([dbc.CardHeader("Найслабша ланка (Напруга)"), dbc.CardBody(html.H3(id="kpi-min-voltage", children=f"{bottleneck_stats_init['min_voltage_str']}"))], color="warning", outline=True), width=4),
                dbc.Col(dbc.Card([dbc.CardHeader("Загальна проп. здатність (абстрактна)"), dbc.CardBody(html.H3(id="kpi-cut-value", children=f"{bottleneck_stats_init['cut_value_str']}"))], color="info", outline=True), width=4),
            ], className="mt-4"),
            # Таблиця
            dbc.Row(dbc.Col([
                html.H5("🔻 Знайдені 'Вузькі місця' (ЛЕП, які треба відключити)", className="text-danger mt-4"),
                # Цей Div оновлюється динамічно
                html.Div(id="output-bottleneck-table",
                         children=format_table(bottleneck_df_init) 
                )
            ], width=12), className="mt-2")
        ]),
        
    ])
], fluid=True) # fluid=True = на всю ширину


# --- ЕТАП 5: CALLBACKS (МОЗОК ДОДАТКУ) ---
# Тут визначається вся інтерактивність дашборду.

@app.callback(
    Output('map-click-store', 'data'), # ВИХІД: Оновити невидиме сховище
    Input('geo-map-graph', 'clickData'), # ВХІД: Слідкувати за кліком на мапі
    prevent_initial_call=True # Не запускати при завантаженні
)
def store_map_click(clickData):
    """
    Callback 1: "Ловить" клік на мапі ('geo-map-graph').
    Витягує ID вузла з 'customdata' та зберігає його у
    невидиме сховище ('map-click-store').
    """
    if not clickData: 
        raise PreventUpdate
    try:
        # 'customdata[0]' містить ID, який ми передали в plotting_plotly.py
        node_id = clickData['points'][0]['customdata'][0]
        print(f"...CALLBACK (Map): Клікнуто вузол {node_id}")
        return node_id
    except (KeyError, IndexError, TypeError):
        print("...CALLBACK (Map): Клік не розпізнано.")
        raise PreventUpdate

@app.callback(
    Output('input-source', 'value'), # ВИХІД: Оновити поле "Джерело"
    Output('input-sink', 'value'),   # ВИХІД: Оновити поле "Споживач"
    Input('map-click-store', 'data'), # ВХІД: Слідкувати за змінами у сховищі
    State('flow-radio-select', 'value'), # СТАН: Перевірити, який перемикач обрано
    State('input-source', 'value'), # СТАН: Взяти поточне значення "Джерела"
    State('input-sink', 'value'),   # СТАН: Взяти поточне значення "Споживача"
    prevent_initial_call=True
)
def update_inputs_from_map(clicked_node_id, radio_choice, current_source, current_sink):
    """
    Callback 2: "Слухає" невидиме сховище.
    Коли 'map-click-store' оновлюється (після кліку на мапі),
    ця функція перевіряє перемикач ('flow-radio-select') і 
    вставляє новий ID у правильне поле ('input-source' або 'input-sink').
    """
    if not clicked_node_id:
        raise PreventUpdate
    
    if radio_choice == 'source':
        print(f"...CALLBACK (Store): Встановлено Джерело = {clicked_node_id}")
        return clicked_node_id, current_sink # Оновити Джерело, залишити Споживача
    elif radio_choice == 'sink':
        print(f"...CALLBACK (Store): Встановлено Споживача = {clicked_node_id}")
        return current_source, clicked_node_id # Залишити Джерело, оновити Споживача
    
    return current_source, current_sink # На випадок, якщо щось піде не так

@app.callback(
    Output('output-bottleneck-table', 'children'), # ВИХІД: Таблиця результатів
    Output('output-flow-error', 'children'),     # ВИХІД: Повідомлення про помилку
    Output('kpi-line-count', 'children'),        # ВИХІД: KPI 1
    Output('kpi-min-voltage', 'children'),       # ВИХІД: KPI 2
    Output('kpi-cut-value', 'children'),         # ВИХІД: KPI 3
    Input('button-calculate-flow', 'n_clicks'),  # ВХІД: Клік на кнопку
    State('input-source', 'value'),              # СТАН: Взяти ID Джерела
    State('input-sink', 'value'),                # СТАН: Взяти ID Споживача
    prevent_initial_call=True 
)
def update_bottleneck_analysis(n_clicks, source_id, sink_id):
    """
    Callback 3: Головний розрахунковий Callback.
    Активується при натисканні кнопки 'button-calculate-flow'.
    Бере ID з полів вводу, викликає 'analysis.get_bottleneck_analysis'
    і оновлює всі 3 виходи: Таблицю, KPI-картки та Повідомлення про помилку.
    """
    
    # 1. Валідація (перевірка) введених даних
    no_update = (dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update) 
    
    if not source_id or not sink_id:
        alert = dbc.Alert("Будь ласка, введіть ID для Джерела та Споживача.", color="danger")
        return dash.no_update, alert, dash.no_update, dash.no_update, dash.no_update
    if source_id not in G_main.nodes:
        alert = dbc.Alert(f"Помилка: ID Джерела '{source_id}' не знайдено в графі.", color="danger")
        return dash.no_update, alert, dash.no_update, dash.no_update, dash.no_update
    if sink_id not in G_main.nodes:
        alert = dbc.Alert(f"Помилка: ID Споживача '{sink_id}' не знайдено в графі.", color="danger")
        return dash.no_update, alert, dash.no_update, dash.no_update, dash.no_update
    if source_id == sink_id:
        alert = dbc.Alert("Джерело та Споживач не можуть бути однаковими.", color="danger")
        return dash.no_update, alert, dash.no_update, dash.no_update, dash.no_update

    # 2. Розрахунок (викликаємо 'analysis.py')
    print(f"...CALLBACK (Button): Розрахунок нового 'вузького місця': {source_id} -> {sink_id}")
    start_time = time.time()
    try:
        new_stats, new_bottleneck_df = analysis.get_bottleneck_analysis(G_main, source_id, sink_id)
        print(f"...CALLBACK (Button): Розрахунок завершено за {time.time() - start_time:.2f} сек.")
    except Exception as e:
        # Обробка помилок NetworkX (напр., немає шляху між вузлами)
        print(f"...CALLBACK (Button): ПОМИЛКА - {e}")
        alert = dbc.Alert(f"Помилка розрахунку: {e}. Можливо, між вузлами немає шляху.", color="danger")
        return dash.no_update, alert, dash.no_update, dash.no_update, dash.no_update

    # 3. Повертаємо результати для оновлення 5 компонентів
    new_table = format_table(new_bottleneck_df)
    kpi1_count = f"{new_stats['line_count']}"
    kpi2_voltage = f"{new_stats['min_voltage_str']}"
    kpi3_capacity = f"{new_stats['cut_value_str']}"
    
    return new_table, None, kpi1_count, kpi2_voltage, kpi3_capacity 


# --- ЕТАП 6: ЗАПУСК GUI ---
if __name__ == '__main__':
    print("-" * 30)
    print("Всі розрахунки завершено. Запускаю Dash-сервер...")
    print("НАТИСНІТЬ CTRL+C, ЩОБ ЗУПИНИТИ ДОДАТОК.")
    print("Відкрийте цей URL у вашому браузері:")
    print("http://127.0.0.1:8050/")
    print("-" * 30)
    
    # debug=False - для стабільної роботи (не перезавантажується)
    app.run(debug=False, port=8050)
