// Mock lightweight-charts v5 — jsdom 不支持 canvas,只 mock 接口
const mockSeries = () => ({
  setData: () => {},
  update: () => {},
  priceScale: () => ({
    applyOptions: () => {},
  }),
});

// 支持 v5 API: chart.addSeries(CandlestickSeries, options)
const createChart = () => ({
  addSeries: (_type, options) => {
    void options;
    return mockSeries();
  },
  remove: () => {},
  applyOptions: () => {},
  timeScale: () => ({ fitContent: () => {} }),
  priceScale: () => ({
    applyOptions: () => {},
  }),
});

const ColorType = { Solid: "solid", VerticalGradient: "vgradient" };
const CandlestickSeries = "CandlestickSeries";
const HistogramSeries = "HistogramSeries";
const LineSeries = "LineSeries";
const AreaSeries = "AreaSeries";

module.exports = {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  AreaSeries,
  ColorType,
  default: { createChart, CandlestickSeries, ColorType },
};
