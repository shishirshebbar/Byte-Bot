import type { Finding } from './investigation-types';

export function highlightedFindings(findings: Finding[]) {
  return [
    findings.find(finding => finding.kind === 'same_destination' && finding.quote)
      ?? findings.find(finding => finding.kind === 'same_destination'),
    findings.find(finding => finding.rule_id === 'extracted-threat')
      ?? findings.find(finding => finding.kind === 'threat'),
    findings.find(finding => finding.rule_id === 'extracted-bank_avoidance')
      ?? findings.find(finding => finding.kind === 'bank_avoidance'),
  ].filter((finding): finding is Finding => !!finding);
}
