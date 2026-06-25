import Breadcrumb from './Breadcrumb'

interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
}

export default function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className="mb-8 flex flex-col gap-0.5 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <Breadcrumb />
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-gray-500">{subtitle}</p>}
      </div>
      {actions && <div className="mt-3 sm:mt-0 shrink-0">{actions}</div>}
    </div>
  )
}
