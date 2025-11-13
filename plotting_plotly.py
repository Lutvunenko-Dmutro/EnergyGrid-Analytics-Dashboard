import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

PLOTLY_TEMPLATE = "plotly_dark" 

def create_histogram_fig(hist_df):
    """
    Малює інтерактивну гістограму розподілу ступенів.
    
    @param hist_df (pd.DataFrame): DataFrame з даними ['Ступінь', 'Кількість вузлів'].
    @return (go.Figure): Готовий об'єкт графіка Plotly.
    """
    fig = px.bar(hist_df, 
                 x='Ступінь', 
                 y='Кількість вузлів',
                 log_y=True, # Логарифмічна шкала для наочності
                 title='Розподіл ступенів вузлів (Логарифмічна шкала)',
                 template=PLOTLY_TEMPLATE)
    
    fig.update_layout(bargap=0.1, 
                      xaxis_title="Ступінь (Кількість підключених ЛЕП)",
                      yaxis_title="Кількість вузлів (Log)")
    
    # Додаємо кастомну підказку при наведенні
    fig.update_traces(marker_color='#5DADE2', hovertemplate='Ступінь: %{x}<br>Кількість: %{y}')
    return fig

def create_robustness_curve_fig(hub_df, rand_df, nodes_to_attack_count):
    """
    Малює інтерактивну криву стійкості, порівнюючи два сценарії.
    
    @param hub_df (pd.DataFrame): Результати цільової атаки.
    @param rand_df (pd.DataFrame): Результати випадкової атаки.
    @param nodes_to_attack_count (int): Кількість атакованих вузлів (для легенди).
    @return (go.Figure): Готовий об'єкт графіка Plotly.
    """
    
    # Об'єднуємо два DataFrame для легкого малювання (Plotly любить "довгий" формат)
    hub_df['Тип атаки'] = f"Цільова (Топ-{nodes_to_attack_count} Хабів)"
    rand_df['Тип атаки'] = f"Випадкова ({nodes_to_attack_count} вузлів)"
    combined_df = pd.concat([hub_df, rand_df])
    
    fig = px.line(combined_df, 
                  x='Крок атаки', 
                  y='Розмір мережі (%)', 
                  color='Тип атаки', # Це створить 2 лінії з легендою
                  title='Крива надійності мережі',
                  template=PLOTLY_TEMPLATE,
                  color_discrete_map={ # Кастомні кольори
                      f"Цільова (Топ-{nodes_to_attack_count} Хабів)": 'red',
                      f"Випадкова ({nodes_to_attack_count} вузлів)": '#5DADE2'
                  })
    
    fig.update_layout(xaxis_title="Кількість видалених вузлів",
                      yaxis_title="% 'живої' мережі",
                      yaxis_range=[0, 105], # від 0% до 105%
                      hovermode="x unified") # Гарна підказка, що показує обидві лінії
    
    # Кастомна підказка
    fig.update_traces(hovertemplate='Крок %{x}: <b>%{y:.2f}%</b>')
    return fig

# --- ОНОВЛЕНА ФУНКЦІЯ ---
def create_geo_voltage_map(voltage_df):
    """
    Малює інтерактивну гео-мапу, розфарбовану за напругою.
    
    @param voltage_df (pd.DataFrame): DataFrame з [lat, lon, text, category, id].
    @return (go.Figure): Готовий об'єкт графіка Plotly Mapbox.
    """
    
    # Визначаємо порядок та кольори
    category_order = ["380кВ+", "220кВ", "110кВ", "Інше (<110кВ)"]
    color_map = {
        "380кВ+": "red",
        "220кВ": "orange",
        "110кВ": "yellow",
        "Інше (<110кВ)": "gray"
    }
    
    fig = px.scatter_mapbox(voltage_df,
                            lat='lat',
                            lon='lon',
                            color='category', # Розфарбовуємо за категорією
                            category_orders={'category': category_order}, # Встановлюємо порядок
                            color_discrete_map=color_map, # Встановлюємо кольори
                            custom_data=['id', 'text'], 
                            title='Гео-мапа підстанцій (за макс. напругою)',
                            template=PLOTLY_TEMPLATE,
                            zoom=3,
                            center=dict(lat=48.0, lon=15.0)
                           )
    
    fig.update_layout(
        mapbox_style="carto-darkmatter", # Темний стиль мапи
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    
    # Оновлюємо, ЩО показувати при наведенні
    fig.update_traces(marker=dict(size=4, opacity=0.5), 
                      hovertemplate='%{customdata[1]}') 
    return fig

def create_hub_voltage_barchart(hubs_composition_df):
    """
    Малює стовпчастий графік складу хабів (stacked bar chart).
    
    @param hubs_composition_df (pd.DataFrame): Дані про склад хабів.
    @return (go.Figure): Готовий об'єкт графіка Plotly.
    """
    
    # Визначаємо порядок та кольори
    category_order = ["380кВ+", "220кВ", "110кВ", "Інше"]
    color_map = {
        "380кВ+": "red",
        "220кВ": "orange",
        "110кВ": "yellow",
        "Інше": "gray"
    }

    fig = px.bar(hubs_composition_df,
                 x='hub_id',
                 y='Кількість ЛЕП',
                 color='Категорія напруги', # Створюємо "stacked" стовпчики
                 title='Склад Топ-10 "Хабів" за напругою ЛЕП',
                 template=PLOTLY_TEMPLATE,
                 category_orders={'Категорія напруги': category_order},
                 color_discrete_map=color_map
                )
    
    fig.update_layout(
        xaxis_title="ID Хаба (загальна кількість ЛЕП)",
        yaxis_title="Кількість ЛЕП"
    )
    # Сортуємо хаби на графіку від найбільшого до найменшого
    fig.update_xaxes(categoryorder='total descending')
    return fig
