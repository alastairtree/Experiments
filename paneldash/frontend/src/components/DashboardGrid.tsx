import { ReactNode } from 'react'
import type { DashboardPanelReference } from '../api/client'

interface DashboardGridProps {
  panels: DashboardPanelReference[]
  columns?: number
  children?: ReactNode | ((panelRef: DashboardPanelReference) => ReactNode)
}

/**
 * Dashboard Grid Layout Component
 *
 * Renders panels in a responsive CSS Grid layout with 12-column system.
 * Supports mobile responsiveness by stacking panels vertically on small screens.
 */
export default function DashboardGrid({ panels, columns = 12, children }: DashboardGridProps) {
  // Render children for each panel if children is a function
  const renderPanel = (panelRef: DashboardPanelReference, _index: number) => {
    if (typeof children === 'function') {
      return (
        <div
          key={panelRef.id}
          className="bg-white rounded-lg shadow p-4 min-h-[200px]"
          data-panel-id={panelRef.id}
        >
          {children(panelRef)}
        </div>
      )
    }
    // Default placeholder if no children function provided
    return (
      <div
        key={panelRef.id}
        className="bg-white rounded-lg shadow p-4 min-h-[200px] flex items-center justify-center"
        data-panel-id={panelRef.id}
      >
        <div className="text-center text-gray-500">
          <h3 className="text-lg font-medium mb-2">Panel: {panelRef.id}</h3>
          <p className="text-sm">Config: {panelRef.config_file}</p>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`
        grid gap-4
        grid-cols-1
        sm:grid-cols-2
        md:grid-cols-3
        lg:grid-cols-${columns}
        auto-rows-min
      `}
      style={{
        // Use inline styles for dynamic grid-template-columns as Tailwind's JIT
        // doesn't support dynamic values in className
        gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
      }}
    >
      {panels.map((panelRef, index) => renderPanel(panelRef, index))}
      {/* Render static children if not a function */}
      {typeof children !== 'function' && children}
    </div>
  )
}
