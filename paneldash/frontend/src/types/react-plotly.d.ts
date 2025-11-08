declare module 'react-plotly.js' {
  import { Component } from 'react'
  import { PlotParams } from 'plotly.js'

  export interface PlotProps extends Partial<PlotParams> {
    data: Plotly.Data[]
    layout?: Partial<Plotly.Layout>
    config?: Partial<Plotly.Config>
    frames?: Plotly.Frame[]
    useResizeHandler?: boolean
    style?: React.CSSProperties
    className?: string
    onInitialized?: (figure: Readonly<Plotly.Figure>, graphDiv: Readonly<HTMLElement>) => void
    onUpdate?: (figure: Readonly<Plotly.Figure>, graphDiv: Readonly<HTMLElement>) => void
    onPurge?: (figure: Readonly<Plotly.Figure>, graphDiv: Readonly<HTMLElement>) => void
    onError?: (err: Readonly<Error>) => void
    onHover?: (event: Readonly<Plotly.PlotMouseEvent>) => void
    onUnhover?: (event: Readonly<Plotly.PlotMouseEvent>) => void
    onClick?: (event: Readonly<Plotly.PlotMouseEvent>) => void
    onSelected?: (event: Readonly<Plotly.PlotSelectionEvent>) => void
    onRelayout?: (event: Readonly<Plotly.PlotRelayoutEvent>) => void
    onRestyle?: (event: Readonly<Plotly.PlotRestyleEvent>) => void
    onRedraw?: () => void
    onAnimated?: () => void
    onLegendClick?: (event: Readonly<Plotly.LegendClickEvent>) => boolean
    onLegendDoubleClick?: (event: Readonly<Plotly.LegendClickEvent>) => boolean
    onSliderChange?: (event: Readonly<Plotly.SliderChangeEvent>) => void
    onSliderEnd?: (event: Readonly<Plotly.SliderEndEvent>) => void
    onSliderStart?: (event: Readonly<Plotly.SliderStartEvent>) => void
    onTransitioning?: () => void
    onTransitionInterrupted?: () => void
    onDoubleClick?: () => void
    onFramework?: () => void
    revision?: number
    divId?: string
    debug?: boolean
  }

  export default class Plot extends Component<PlotProps> {}
}
