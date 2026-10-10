export type GrievancePriority = 'high' | 'normal';

const HIGH = [
  'urgent', 'emergency', 'accident', 'died', 'death', 'flood', 'fire', 'no water', 'drinking water',
  'electricity', 'power cut', 'current cut', 'attack', 'blood', 'ambulance', 'hospital', 'danger',
  'suicide', 'protest', 'riot', 'collapse', 'injury', 'injured', 'not working',
  'అత్యవసర', 'ప్రమాద', 'మరణ', 'వరద', 'అగ్ని', 'నీళ్లు', 'కరెంట్',
];

/** High when the words describe an urgent problem. Otherwise normal. */
export function classifyGrievance(value: string): { priority: GrievancePriority; sentiment: 'negative' | 'neutral' } {
  const hay = value.toLowerCase();
  const high = HIGH.some((word) => hay.includes(word));
  return { priority: high ? 'high' : 'normal', sentiment: high ? 'negative' : 'neutral' };
}

export function priorityLabel(priority: GrievancePriority): string {
  return priority === 'high' ? 'High priority' : 'Normal';
}

export const MOCK_GRIEVANCES: Array<{ title: string; detail: string; priority: GrievancePriority }> = [
  { title: 'No drinking water', detail: 'Vinukonda colony has had no water for two days.', priority: 'high' },
  { title: 'Road damage', detail: 'The main road near Narasaraopet bus stand is broken.', priority: 'high' },
  { title: 'Street lights', detail: 'Lights are out on the Chilakaluripet market road.', priority: 'normal' },
  { title: 'Pension delay', detail: 'A pension has not arrived in Sattenapalle this month.', priority: 'normal' },
];
