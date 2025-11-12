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

  const column_map = {
    1: 'col-span-1',
    2: 'col-span-2',
    3: 'col-span-3',
    4: 'col-span-4',
    5: 'col-span-5',
    6: 'col-span-6',
    7: 'col-span-7',
    8: 'col-span-8',
    9 : 'col-span-9',
    10: 'col-span-10',
    11: 'col-span-11',
    12: 'col-span-12',
  };

  const height_map = {
    1: 'min-h-[100px]',
    2: 'min-h-[200px]',
    3: 'min-h-[300px]',
    4: 'min-h-[400px]',
    5: 'min-h-[500px]',
    6: 'min-h-[600px]',
    7: 'min-h-[700px]',
    8: 'min-h-[800px]',
    9: 'min-h-[900px]',
    10: 'min-h-[1000px]',
  };

  function getHeightClass(height: number | undefined): string {
    if (!height) return 'min-h-[200px]'; // default height
    return height_map[height] || 'min-h-[100px]';
  }

  // Render children for each panel if children is a function
  const renderPanel = (panelRef: DashboardPanelReference, _index: number) => {
    if (typeof children === 'function') {
      return (
        <div
          key={panelRef.id}
          className={`bg-white rounded-lg shadow p-4 min-h-[200px] ${column_map[panelRef.position.width] || "col-span-12"} ${getHeightClass(panelRef.position.height)}`}
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
