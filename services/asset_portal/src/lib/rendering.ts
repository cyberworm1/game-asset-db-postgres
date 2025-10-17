import apiClient from './apiClient';

export interface RenderStatusSummary {
  cued: number;
  running: number;
  success: number;
  fail: number;
}

export interface OpenCueSummaryResponse {
  enabled: boolean;
  available: boolean;
  summary: RenderStatusSummary;
  last_updated: string;
  source?: string | null;
  message?: string | null;
}

export interface OpenCueJobDetail {
  id?: string | null;
  name?: string | null;
  show?: string | null;
  shot?: string | null;
  layer?: string | null;
  user?: string | null;
  status: string;
  host?: string | null;
  started_at?: string | null;
  updated_at?: string | null;
  frame_count?: number | null;
  running_frames?: number | null;
  succeeded_frames?: number | null;
  failed_frames?: number | null;
}

export interface OpenCueDetailedResponse extends OpenCueSummaryResponse {
  jobs: OpenCueJobDetail[];
}

export const fetchOpenCueSummary = async (): Promise<OpenCueSummaryResponse> => {
  const { data } = await apiClient.get<OpenCueSummaryResponse>('/render/opencue/summary');
  return data;
};

export const fetchOpenCueDetails = async (): Promise<OpenCueDetailedResponse> => {
  const { data } = await apiClient.get<OpenCueDetailedResponse>('/render/opencue/details');
  return data;
};

export const statusToColor = (status: string): string => {
  const normalized = status.toLowerCase();
  switch (normalized) {
    case 'running':
      return 'blue';
    case 'success':
      return 'green';
    case 'fail':
      return 'red';
    case 'cued':
    default:
      return 'purple';
  }
};
