export function masteryColor(mastery: number) {
  if (mastery < 60) return "#ef4444";   // red
  if (mastery < 80) return "#f59e0b";   // amber
  return "#22c55e";                    // green
}

export function masteryLabel(mastery: number) {
  if (mastery < 60) return "薄弱";
  if (mastery < 80) return "待提升";
  return "良好";
}

export function levelLabel(level: number) {
  const labels = ["", "入门", "基础", "合格", "良好", "优秀"];
  return labels[level] || `${level}级`;
}
