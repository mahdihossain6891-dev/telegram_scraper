"use client";

import { BehavioralAnalyticsApp } from "@/components/behavioral/BehavioralAnalyticsApp";

/**
 * Isolated Behavioral Analytics route.
 * Does not mount DashboardApp or share page state with the Threat Console SPA.
 */
export default function BehavioralAnalyticsPage() {
  return <BehavioralAnalyticsApp />;
}
