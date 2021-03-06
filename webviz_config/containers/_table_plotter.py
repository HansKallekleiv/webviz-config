import numpy as np
import pandas as pd
from collections import OrderedDict
from pathlib import Path
from uuid import uuid4
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output
import plotly.express as px
from . import WebvizContainer
from ..webviz_store import webvizstore
from ..common_cache import cache


class TablePlotter(WebvizContainer):
    '''### TablePlotter

This container adds a plotter to the webviz instance, using tabular data from
a provided csv file. If feature is requested, the data could also come from
a database.

* `csv_file`: Path to the csv file containing the tabular data. Either absolute
              path or relative to the configuration file.
* `plot_options`: A dictionary of plot options to initialize the plot with
* `lock`: If `True`, only the plot is shown, all dropdowns for changing
          plot options are hidden.
'''

    def __init__(self, app, csv_file: Path, plot_options: dict = None,
                 lock: bool = False):

        self.plot_options = plot_options if plot_options else {}
        self.graph_id = f'graph-id{uuid4()}'
        self.lock = lock
        self.csv_file = csv_file
        self.data = get_data(self.csv_file)
        self.columns = list(self.data.columns)
        self.numeric_columns = list(
            self.data.select_dtypes(include=[np.number]).columns)
        self.selector_row = f'selector-row{uuid4()}'
        self.plot_option_id = f'plot-option{uuid4()}'
        self.set_callbacks(app)

    def add_webvizstore(self):
        return [(get_data, [{'csv_file': self.csv_file}])]

    @property
    def plots(self):
        '''A list of available plots and their options'''
        return {
            'scatter': ['x', 'y', 'size', 'color', 'facet_col'],
            'histogram': ['x', 'y', 'color', 'facet_col', 'barmode',
                          'barnorm', 'histnorm'],
            'bar': ['x', 'y', 'color', 'facet_col'],
            'scatter_3d': ['x', 'y', 'z', 'size', 'color'],
            'line': ['x', 'y', 'color', 'line_group', 'facet_col'],
            'line_3d': ['x', 'y', 'z', 'color'],
            'box': ['x', 'y', 'color', 'facet_col'],
            'violin': ['x', 'y', 'color', 'facet_col'],
            'scatter_matrix': ['dimensions', 'size', 'color'],
            'parallel_coordinates': ['dimensions'],
            'parallel_categories': ['dimensions'],
            'density_contour': ['x', 'y', 'color', 'facet_col'],
        }

    @property
    def plot_args(self):
        '''A list of possible plot options and their default values'''
        return OrderedDict(
            {
                'x': {
                    'options': self.columns,
                    'value': self.plot_options.get('x', self.columns[0]),
                    'multi': False
                },
                'y': {
                    'options': self.columns,
                    'value': self.plot_options.get('y', self.columns[0]),
                    'multi': False
                },
                'z': {
                    'options': self.columns,
                    'value': self.plot_options.get('z', self.columns[0]),
                    'multi': False
                },
                'size': {
                    'options': self.numeric_columns,
                    'value': self.plot_options.get('size', None),
                    'multi': False
                },
                'color': {
                    'options': self.columns,
                    'value': self.plot_options.get('color', None),
                    'multi': False
                },
                'facet_col': {
                    'options': self.columns,
                    'value': self.plot_options.get('facet_col', None),
                    'multi': False
                },
                'line_group': {
                    'options': self.columns,
                    'value': self.plot_options.get('line_group', None),
                    'multi': False
                },
                'barmode': {
                    'options': ['stack', 'group', 'overlay', 'relative'],
                    'value': self.plot_options.get('barmode', 'stack'),
                    'multi': False
                },
                'barnorm': {
                    'options': ['fraction', 'percent'],
                    'value': self.plot_options.get('barnorm', None),
                    'multi': False
                },
                'histnorm': {
                    'options': ['percent', 'propability', 'density',
                                'propability density'],
                    'value': self.plot_options.get('histnorm', None),
                    'multi': False
                },
                'trendline': {
                    'options': self.numeric_columns,
                    'value': None,
                    'multi': False
                },
                'dimensions': {
                    'options': self.columns,
                    'value': self.plot_options.get('dimensions', self.columns),
                    'multi': True
                }

            })

    def plot_option_layout(self):
        '''Renders a dropdown widget for each plot option'''
        divs = []
        # The plot type dropdown is handled separate
        divs.append(
            html.Div(
                style=self.style_options_div,
                children=[
                    html.P('Plot type'),
                    dcc.Dropdown(
                        id=f'{self.plot_option_id}-plottype',
                        clearable=False,
                        options=[{'label': i, 'value': i}
                                 for i in self.plots.keys()],
                        value=self.plot_options.get('type', 'scatter')
                    )
                ]
            )
        )
        # Looping through all available plot options
        # and renders a dropdown widget
        for key, arg in self.plot_args.items():
            divs.append(
                html.Div(
                    style=self.style_options_div,
                    id=f'{self.plot_option_id}-div-{key}',
                    children=[
                        html.P(key),
                        dcc.Dropdown(
                            id=f'{self.plot_option_id}-{key}',
                            clearable=False,
                            options=[{'label': i, 'value': i}
                                     for i in arg['options']],
                            value=arg['value'],
                            multi=arg['multi'])
                    ])
            )
        return divs

    @property
    def style_options_div(self):
        '''Style for active plot options'''
        return {
            'display': 'grid',
        }

    @property
    def style_options_div_hidden(self):
        '''Style for hidden plot options'''
        return {
            'display': 'none',
        }

    @property
    def style_page_layout(self):
        '''Simple grid layout for the page'''
        return {} if self.lock else {
            'display': 'grid',
            'align-content': 'space-around',
            'justify-content': 'space-between',
            'grid-template-columns': '1fr 5fr'
        }

    @property
    def style_selectors(self):
        return {'display': 'none'} if self.lock else {}

    @property
    def layout(self):
        return html.Div(children=[
            html.Div(style=self.style_page_layout, children=[
                html.Div(
                    id=self.selector_row,
                    style=self.style_selectors,
                    children=self.plot_option_layout()),
                html.Div(style={'height': '100%'},
                         children=dcc.Graph(id=self.graph_id, config={
                             'responsive': 'true'})
                         )
            ])
        ])

    @property
    def plot_output_callbacks(self):
        '''Creates list of output dependencies for callback
        The outputs are the graph, and the style of the plot options'''
        outputs = []
        outputs.append(
            Output(self.graph_id, 'figure')
        )
        for plot_arg in self.plot_args.keys():
            outputs.append(
                Output(f'{self.plot_option_id}-div-{plot_arg}', 'style')
            )
        return outputs

    @property
    def plot_input_callbacks(self):
        '''Creates list of input dependencies for callback
        The inputs are the plot type and the current value
        for each plot option
        '''
        inputs = []
        inputs.append(
            Input(f'{self.plot_option_id}-plottype', 'value'))
        for plot_arg in self.plot_args.keys():
            inputs.append(Input(f'{self.plot_option_id}-{plot_arg}', 'value'))
        return inputs

    def set_callbacks(self, app):
        @app.callback(self.container_data_output,
                      [self.container_data_requested])
        def _user_download_data(data_requested):
            return WebvizContainer.container_data_compress(
                [{'filename': 'table_plotter.csv',
                  'content': get_data(self.csv_file).to_csv()}]
            ) if data_requested else ''

        @app.callback(
            self.plot_output_callbacks,
            self.plot_input_callbacks)
        def _update_output(*args):
            '''Updates the graph and shows/hides plot options'''
            plot_type = args[0]
            plotfunc = getattr(px._chart_types, plot_type)
            plotargs = {}
            div_style = []
            for name, plot_arg in zip(self.plot_args.keys(), args[1:]):
                if name in self.plots[plot_type]:
                    plotargs[name] = plot_arg
                    div_style.append(self.style_options_div)
                else:
                    div_style.append(self.style_options_div_hidden)
            return (plotfunc(self.data, **plotargs), *div_style)


@cache.memoize(timeout=cache.TIMEOUT)
@webvizstore
def get_data(csv_file) -> pd.DataFrame:
    return pd.read_csv(csv_file, index_col=None)
