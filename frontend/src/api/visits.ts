import client from './client';
import type { FractureSegment, Visit, CreateVisitRequest } from './types';

export const getVisits = async (ehrId: string, date?: string): Promise<Visit[]> => {
  const { data } = await client.get(`/patients/${ehrId}/visits`, {
    params: date ? { date } : undefined,
  });
  return data;
};

export const getVisit = async (ehrId: string, visitId: number): Promise<Visit> => {
  const { data } = await client.get(`/patients/${ehrId}/visits/${visitId}`);
  return data;
};

export const createVisit = async (ehrId: string, body: CreateVisitRequest): Promise<Visit> => {
  const { data } = await client.post(`/patients/${ehrId}/visits`, body);
  return data;
};

export const deleteVisit = async (ehrId: string, visitId: number): Promise<void> => {
  await client.delete(`/patients/${ehrId}/visits/${visitId}`);
};

export const uploadTriage = async (ehrId: string, visitId: number, file: File): Promise<Visit> => {
  const form = new FormData();
  form.append('file', file);
  const { data } = await client.put(`/patients/${ehrId}/visits/${visitId}/triage`, form);
  return data;
};

export const uploadReport = async (ehrId: string, visitId: number, file: File): Promise<Visit> => {
  const form = new FormData();
  form.append('file', file);
  const { data } = await client.put(`/patients/${ehrId}/visits/${visitId}/report`, form);
  return data;
};

export const uploadXray = async (ehrId: string, visitId: number, file: File): Promise<Visit> => {
  const form = new FormData();
  form.append('file', file);
  const { data } = await client.put(`/patients/${ehrId}/visits/${visitId}/xray`, form);
  return data;
};

export const analyzeXray = async (ehrId: string, visitId: number, filename: string): Promise<Visit> => {
  const { data } = await client.post(`/patients/${ehrId}/visits/${visitId}/xray/${encodeURIComponent(filename)}/analyze`);
  return data;
};

export const saveAnnotations = async (
  ehrId: string,
  visitId: number,
  filename: string,
  segments: FractureSegment[],
): Promise<Visit> => {
  const { data } = await client.put(
    `/patients/${ehrId}/visits/${visitId}/xray/${encodeURIComponent(filename)}/annotations`,
    { segments },
  );
  return data;
};

export const saveReport = async (ehrId: string, visitId: number, filename: string, markdown: string): Promise<Visit> => {
  const file = new File([markdown], filename, { type: 'text/markdown' });
  const form = new FormData();
  form.append('file', file);
  const { data } = await client.put(`/patients/${ehrId}/visits/${visitId}/report`, form);
  return data;
};

export const getFileUrl = (
  ehrId: string,
  visitId: number,
  type: 'triage' | 'report' | 'xray',
  filename: string,
): string => {
  const base = import.meta.env.VITE_API_URL ?? 'http://localhost:8080/api';
  return `${base}/patients/${ehrId}/visits/${visitId}/${type}/${filename}`;
};
