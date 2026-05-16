import type { Patient } from './types';

const LLM_BASE = (import.meta.env.VITE_LLM_URL ?? 'http://localhost:8082').replace(/\/$/, '');

export const analyzeWithLLM = async (
  text: string,
  patient: Patient,
  category: string,
  triagePdfUrl: string | null,
  options?: {
    imageFile?: File | null;
    audioFile?: File | null;
    audioLanguage?: string | null;
  },
): Promise<string> => {
  const form = new FormData();
  const todaysDate = new Date().toLocaleDateString('en-CA');
  // Append image first when present (Gemma recommends image first in multimodal messages)
  if (options?.imageFile) {
    form.append('image', options.imageFile);
  }
  form.append('text', `today's date is: ${todaysDate}\n${text}`);
  form.append('category', category);
  form.append('user_id', patient.ehrId);
  form.append('metadata_json', JSON.stringify({
    firstName: patient.firstName,
    lastName: patient.lastName,
    age: patient.age,
    gender: patient.gender,
  }));

  if (triagePdfUrl) {
    const triageResp = await fetch(triagePdfUrl);
    if (triageResp.ok) {
      const blob = await triageResp.blob();
      const filename = triagePdfUrl.split('/').pop() ?? 'triage.pdf';
      form.append('pdf', new File([blob], filename, { type: 'application/pdf' }));
    }
  }

  // image already appended above if provided

  if (options?.audioFile) {
    // Send the recorded audio as both `stt_file` (backend param) and `audio`.
    form.append('stt_file', options.audioFile);
    form.append('audio', options.audioFile);
    // Signal to the server that the audio language is English for transcription.
    form.append('audio_language', 'en');
  }

  console.log(form)
  const resp = await fetch(`${LLM_BASE}/analyze`, { method: 'POST', body: form });
  if (!resp.ok) throw new Error(`LLM error ${resp.status}: ${await resp.text()}`);
  return resp.text();
};
