import { useState } from 'react';
import { Card, Typography, Alert, Spin } from 'antd';
import Plot from 'react-plotly.js';
import { extractLocalName, metadataToJsonKey, findKeyIgnoreCase, findEndpointPath } from '../../../lib/utils.js';
import ParameterForm from './ParameterForm.jsx';

const { Title, Text } = Typography;

// Map graph types from ontology to Plotly types
const PLOTLY_TYPE_MAP = {
  LinePlot: 'scatter',
  BarPlot: 'bar',
  CircularPlot: 'pie',
  Graph: 'scatter',  // Default fallback
};

// Map graph types to Plotly mode (for scatter plots)
const PLOTLY_MODE_MAP = {
  LinePlot: 'lines+markers',
  BarPlot: undefined,  // Not used for bar
  CircularPlot: undefined,  // Not used for pie
  Graph: 'lines+markers',
};

// Default colors for multiple series
const SERIES_COLORS = [
  '#1f77b4',  // Blue
  '#ff7f0e',  // Orange
  '#2ca02c',  // Green
  '#d62728',  // Red
  '#9467bd',  // Purple
  '#8c564b',  // Brown
  '#e377c2',  // Pink
  '#7f7f7f',  // Gray
];

// Get value from object using case-insensitive key matching
function getValueIgnoreCase(obj, searchKey) {
  const actualKey = findKeyIgnoreCase(obj, searchKey);
  return actualKey ? obj[actualKey] : undefined;
}

// Generate display label for a series from metadata name
// e.g., "Temperature2m_R" -> "Temperature 2m"
function generateSeriesLabel(metadataName) {
  if (!metadataName) return 'Unknown';

  // Remove "_R" suffix
  let label = metadataName.replace(/_R$/, '');

  // Add space before numbers and uppercase letters
  label = label
    .replace(/(\d+)/g, ' $1')
    .replace(/([A-Z])/g, ' $1')
    .trim()
    .replace(/\s+/g, ' ');

  return label;
}

// Parse alias entries in the format "MetadataLocalName=Display Label".
function parseSeriesAliases(seriesAliases) {
  const aliasMap = {};
  const aliases = Array.isArray(seriesAliases) ? seriesAliases : [seriesAliases].filter(Boolean);

  aliases.forEach((entry) => {
    if (typeof entry !== 'string') return;

    const separatorIndex = entry.indexOf('=');
    if (separatorIndex === -1) return;

    const rawKey = entry.slice(0, separatorIndex).trim();
    const displayLabel = entry.slice(separatorIndex + 1).trim();
    if (!rawKey || !displayLabel) return;

    const metadataLocalName = extractLocalName(rawKey);
    const jsonKey = metadataToJsonKey(metadataLocalName || rawKey);

    aliasMap[rawKey] = displayLabel;
    if (metadataLocalName) aliasMap[metadataLocalName] = displayLabel;
    if (jsonKey) aliasMap[jsonKey] = displayLabel;
  });

  return aliasMap;
}

export default function GraphComponent({
  graph,
  title,
  graphType = 'LinePlot',
  bm,
  xAxis,
  yAxes = [],
  seriesAliases = [],
  xAxisLabel,
  yAxisLabel,
  legendPosition = 'bottom',
  parameters,
  endpointPaths,
  apiBaseUrl,
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [plotData, setPlotData] = useState(null);

  const graphName = graph?.split('#')[1] || graph?.split('/').pop() || 'Graph';
  const displayTitle = title || graphName;
  const bmLocalName = bm?.split('#')[1] || bm?.split('/').pop() || '';
  const endpointPath = findEndpointPath(endpointPaths, bmLocalName);
  const seriesAliasMap = parseSeriesAliases(seriesAliases);

  // Process API response data into Plotly format
  const processDataForPlot = (apiData) => {
    console.log('=== DEBUG: Processing API Data ===');
    console.log('Raw API Data:', apiData);
    console.log('Is Array:', Array.isArray(apiData));

    // Get the x-axis key from metadata URI
    const xMetadataName = extractLocalName(xAxis);
    const xKey = metadataToJsonKey(xMetadataName);
    console.log('X-axis metadata name:', xMetadataName);
    console.log('X-axis JSON key:', xKey);

    // Ensure yAxes is an array
    const yAxisArray = Array.isArray(yAxes) ? yAxes : [yAxes].filter(Boolean);
    console.log('Y-axes URIs:', yAxisArray);

    // Resolve the data source: the plottable array may be at the top level
    // or nested inside a wrapper key (e.g., "WeatherData", "results", etc.)
    let dataArray = null;

    if (Array.isArray(apiData)) {
      dataArray = apiData;
    } else {
      // Search for the first array of objects that contains the expected xKey
      for (const val of Object.values(apiData)) {
        if (Array.isArray(val) && val.length > 0 && typeof val[0] === 'object' && findKeyIgnoreCase(val[0], xKey)) {
          dataArray = val;
          break;
        }
      }
    }

    let xValues = [];
    let yValuesMap = {};

    if (dataArray && dataArray.length > 0) {
      console.log('Data source resolved: array with', dataArray.length, 'items');
      console.log('First item keys:', Object.keys(dataArray[0]));

      xValues = dataArray.map(item => getValueIgnoreCase(item, xKey));
      console.log('X values extracted:', xValues.length, 'items, first value:', xValues[0]);

      yAxisArray.forEach((yMetadataUri) => {
        const yMetadataName = extractLocalName(yMetadataUri);
        const yKey = metadataToJsonKey(yMetadataName);
        yValuesMap[yKey] = dataArray.map(item => getValueIgnoreCase(item, yKey));
        console.log(`Y-axis "${yKey}" first value:`, yValuesMap[yKey][0]);
      });
    } else {
      console.warn('Could not find a data array containing the expected x-axis key:', xKey);
    }

    console.log('X values count:', xValues.length);

    // Build traces for each y-axis metadata
    const traces = yAxisArray.map((yMetadataUri, index) => {
      const yMetadataName = extractLocalName(yMetadataUri);
      const yKey = metadataToJsonKey(yMetadataName);
      const aliasLabel = seriesAliasMap[yMetadataUri] || seriesAliasMap[yMetadataName] || seriesAliasMap[yKey];
      const seriesLabel = aliasLabel || generateSeriesLabel(yMetadataName);
      const yValues = yValuesMap[yKey] || [];

      console.log(`Series ${index}: metadata=${yMetadataName}, jsonKey=${yKey}, values=${yValues.length}`);

      const plotlyType = PLOTLY_TYPE_MAP[graphType] || 'scatter';
      const plotlyMode = PLOTLY_MODE_MAP[graphType];

      const trace = {
        x: xValues,
        y: yValues,
        type: plotlyType,
        name: seriesLabel,
        marker: { color: SERIES_COLORS[index % SERIES_COLORS.length] },
      };

      if (plotlyMode) {
        trace.mode = plotlyMode;
      }

      // For pie charts, use different structure
      if (graphType === 'CircularPlot') {
        return {
          values: yValues,
          labels: xValues,
          type: 'pie',
          name: seriesLabel,
        };
      }

      return trace;
    });

    console.log('Final traces:', traces);
    return traces;
  };

  const handleSuccess = (data) => {
    const traces = processDataForPlot(data);
    const hasData = traces.some(t => t.x?.length > 0 || t.values?.length > 0);

    if (hasData) {
      setPlotData(traces);
    } else {
      setError(data.desc || data.detail || 'The API returned no plottable data.');
    }
  };

  const handleError = (msg) => {
    setError(msg);
  };

  // Generate axis labels
  const xLabel = xAxisLabel || generateSeriesLabel(extractLocalName(xAxis)) || 'X Axis';
  const yLabel = yAxisLabel || 'Value';
  const selectedLegendPosition = legendPosition === 'bottom' ? 'bottom' : 'right';

  const legendPresets = {
    bottom: {
      legend: { orientation: 'h', x: 0.5, y: -0.28, xanchor: 'center', yanchor: 'top' },
      margin: { l: 80, r: 40, t: 80, b: 140 },
    },
    right: {
      legend: { orientation: 'v', x: 1.02, y: 0.5, xanchor: 'left', yanchor: 'middle' },
      margin: { l: 80, r: 220, t: 80, b: 80 },
    },
  };
  const selectedLegend = legendPresets[selectedLegendPosition];

  // Plotly layout configuration
  const layout = {
    title: {
      text: displayTitle,
      font: { size: 18 },
    },
    xaxis: {
      title: {
        text: xLabel,
        standoff: 16,
      },
      automargin: true,
    },
    yaxis: {
      title: {
        text: yLabel,
        standoff: 12,
      },
      automargin: true,
    },
    legend: selectedLegend.legend,
    autosize: true,
    margin: selectedLegend.margin,
  };

  const plotConfig = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
  };

  return (
    <Card
      title={<Title level={4} style={{ margin: 0 }}>{displayTitle}</Title>}
      style={{ marginBottom: 16 }}
    >
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        Graph Type: {graphType} | Endpoint: POST {endpointPath}
      </Text>

      <ParameterForm
        bm={bm}
        endpointPath={endpointPath}
        apiBaseUrl={apiBaseUrl}
        parameters={parameters}
        onSuccess={handleSuccess}
        onError={handleError}
        onLoadingChange={setLoading}
      />

      {error && (
        <Alert
          type="error"
          message="Error"
          description={error}
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setError(null)}
        />
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <Text style={{ display: 'block', marginTop: 16 }}>Loading data...</Text>
        </div>
      )}

      {plotData && !loading && (
        <div style={{ width: '100%', minHeight: 400 }}>
          <Plot
            data={plotData}
            layout={layout}
            config={plotConfig}
            style={{ width: '100%', height: '100%' }}
            useResizeHandler={true}
          />
        </div>
      )}

      {!plotData && !loading && !error && (
        <div style={{
          textAlign: 'center',
          padding: 40,
          background: '#fafafa',
          borderRadius: 8,
          border: '1px dashed #d9d9d9'
        }}>
          <Text type="secondary">
            Enter the parameters above and click &quot;Load Data&quot; to display the graph.
          </Text>
        </div>
      )}
    </Card>
  );
}
