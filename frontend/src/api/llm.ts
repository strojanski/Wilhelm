const LLM_BASE = import.meta.env.VITE_LLM_URL ?? 'http://localhost:8080';

export const analyzeWithLLM = async (
  imageUrl: string,
  patientContext: string,
): Promise<string> => {
  const imgResp = await fetch(imageUrl);
  if (!imgResp.ok) throw new Error('Failed to fetch X-ray image');
  const blob = await imgResp.blob();
  const ext = imageUrl.split('.').pop()?.toLowerCase() ?? 'jpg';
  const file = new File([blob], `xray.${ext}`, { type: blob.type || 'image/jpeg' });

  const form = new FormData();
  form.append('image', file);
  form.append('text', patientContext);
  form.append('category', 'radiology');

  const resp = await fetch(`${LLM_BASE}/analyze`, { method: 'POST', body: form });
  if (!resp.ok) throw new Error(`LLM error ${resp.status}: ${await resp.text()}`);

  // Treat the response body as raw markdown
  return resp.text();
};
