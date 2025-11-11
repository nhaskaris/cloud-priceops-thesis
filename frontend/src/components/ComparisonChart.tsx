// ComparisonChart displays provider monthly cost in USD
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'
import { Bar } from 'react-chartjs-2'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

type Result = {
  provider: string
  monthly_cost: number | null
}

type Props = {
  results: Result[]
}

export default function ComparisonChart({ results }: Props) {
  const labels = results.map((r) => r.provider.toUpperCase())
  const data = {
    labels,
    datasets: [
      {
        label: `Monthly cost (USD)`,
        data: results.map((r) => (r.monthly_cost != null ? Number(r.monthly_cost) : 0)),
        backgroundColor: ['#4f46e5', '#10b981', '#f97316'],
      },
    ],
  }

  const options: any = {
    responsive: true,
    plugins: {
      legend: { position: 'top' as const },
      title: { display: true, text: `Provider monthly cost comparison (USD)` },
      tooltip: {
        callbacks: {
          label: function (context: any) {
            const v = context.parsed && (context.parsed.y ?? context.parsed)
            if (v == null) return 'N/A'
            return `$${Number(v).toFixed(2)}`
          },
        },
      },
    },
    scales: {
      y: { beginAtZero: true },
    },
  }

  return (
    <div style={{ maxWidth: 720, margin: '1.5rem auto' }}>
      <Bar options={options} data={data} />
    </div>
  )
}
