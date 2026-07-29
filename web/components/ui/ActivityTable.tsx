"use client";

import type { ReactNode } from "react";

type Column = {
  key: string;
  header: string;
  className?: string;
};

type ActivityTableProps<T extends Record<string, unknown>> = {
  columns: Column[];
  rows: T[];
  renderCell: (row: T, columnKey: string) => ReactNode;
  emptyMessage?: string;
  rowKey: (row: T) => string | number;
  className?: string;
};

export function ActivityTable<T extends Record<string, unknown>>({
  columns,
  rows,
  renderCell,
  emptyMessage = "No activity in scope.",
  rowKey,
  className = "",
}: ActivityTableProps<T>) {
  if (!rows.length) {
    return <div className="empty-state">{emptyMessage}</div>;
  }

  return (
    <div className={`table-wrap activity-table ${className}`.trim()}>
      <table>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} className={col.className}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((col) => (
                <td key={col.key} className={col.className}>
                  {renderCell(row, col.key)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
