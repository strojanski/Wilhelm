import type { Patient } from './types';

const LLM_BASE = (import.meta.env.VITE_LLM_URL ?? 'http://localhost:8082').replace(/\/$/, '');

export const analyzeWithLLM = async (
  text: string,
  patient: Patient,
  category: string,
  triagePdfUrl: string | null,
): Promise<string> => {
  const form = new FormData();
  const todaysDate = new Date().toLocaleDateString('en-CA');
  form.append('text', `today's date is: ${todaysDate}\n${text}`);
  form.append('category', category);
  form.append('user_id', patient.ehrId);
  form.append('metadata_json', JSON.stringify({
    firstName: patient.firstName,
    lastName:  patient.lastName,
    age:       patient.age,
    gender:    patient.gender,
  }));

  if (triagePdfUrl) {
    const triageResp = await fetch(triagePdfUrl);
    if (triageResp.ok) {
      const blob = await triageResp.blob();
      const filename = triagePdfUrl.split('/').pop() ?? 'triage.pdf';
      form.append('pdf', new File([blob], filename, { type: 'application/pdf' }));
    }
  }

  const resp = await fetch(`${LLM_BASE}/analyze`, { method: 'POST', body: form });
  if (!resp.ok) throw new Error(`LLM error ${resp.status}: ${await resp.text()}`);
  return resp.text();
};
