import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import type { IndustryAllocation } from '../types';

ChartJS.register(ArcElement, Tooltip, Legend);

interface Props {
  data: IndustryAllocation[];
}

const AllocationChart = ({ data }: Props) => {
  if (data.length === 0) {
    return <p className="no-data">No allocation data available</p>;
  }

  const colors = [
    '#3b82f6', // blue
    '#10b981', // green
    '#f59e0b', // amber
    '#ef4444', // red
    '#8b5cf6', // purple
    '#ec4899', // pink
    '#14b8a6', // teal
    '#f97316', // orange
  ];

  const chartData = {
    labels: data.map((item) => item.industry),
    datasets: [
      {
        data: data.map((item) => item.percentage),
        backgroundColor: colors.slice(0, data.length),
        borderColor: '#fff',
        borderWidth: 2,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'right' as const,
      },
      tooltip: {
        callbacks: {
          label: function (context: any) {
            const label = context.label || '';
            const value = context.parsed || 0;
            return `${label}: ${value.toFixed(2)}%`;
          },
        },
      },
    },
  };

  return (
    <div className="chart-container">
      <Pie data={chartData} options={options} />
    </div>
  );
};

export default AllocationChart;
