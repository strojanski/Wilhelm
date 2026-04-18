import client from './client';
import type { Patient, PatientPage, CreatePatientRequest } from './types';

export const getPatients = async (page = 0, size = 20): Promise<PatientPage> => {
  const { data } = await client.get('/patients', { params: { page, size, sort: 'lastName,asc' } });
  return data;
};

export const getPatient = async (ehrId: string): Promise<Patient> => {
  const { data } = await client.get(`/patients/${ehrId}`);
  return data;
};

export const createPatient = async (body: CreatePatientRequest): Promise<Patient> => {
  const { data } = await client.post('/patients', body);
  return data;
};

export const deletePatient = async (ehrId: string): Promise<void> => {
  await client.delete(`/patients/${ehrId}`);
};
