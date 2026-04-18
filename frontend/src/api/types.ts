export type Gender = 'MALE' | 'FEMALE' | 'OTHER';

export interface Patient {
  id: number;
  firstName: string;
  lastName: string;
  ehrId: string;
  age: number;
  gender: Gender;
}

export interface PatientPage {
  content: Patient[];
  totalElements: number;
  totalPages: number;
  number: number;
  size: number;
}

export interface FractureSegment {
  annId: number;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
  iouScore: number;
  userCorrected: boolean;
  maskB64?: string; // base64-encoded PNG mask from SAM-Med2D
}

export interface XrayAnalysis {
  segments: FractureSegment[];
  analyzedAt: string;
  corrected: boolean;
}

export interface Visit {
  id: number;
  patientEhrId: string;
  visitDate: string;
  createdAt: string;
  triageFiles: string[];
  reportFiles: string[];
  xrayFiles: string[];
  xrayAnnotations: Record<string, XrayAnalysis>;
}

export interface CreatePatientRequest {
  firstName: string;
  lastName: string;
  ehrId: string;
  age: number;
  gender: Gender;
}

export interface CreateVisitRequest {
  visitDate: string;
}

export interface ApiError {
  status: number;
  error: string;
  message: string;
  timestamp: string;
}
