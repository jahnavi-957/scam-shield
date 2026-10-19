import { useMutation, useQuery } from '@tanstack/react-query';
import {
  analyzeScreenshot,
  analyzeText,
  getEntityHistory,
  getPresignedUploadUrl,
  uploadToS3,
} from '../api/client';
import type { AnalysisResponse, EntityHistoryResponse } from '../api/client';
import { queryKeys } from '../api/queryClient';

// --------------------------------------------------------------------------- #
// Text analysis
// --------------------------------------------------------------------------- #

export function useAnalyzeText() {
  return useMutation<AnalysisResponse, Error, string>({
    mutationFn: analyzeText,
  });
}

// --------------------------------------------------------------------------- #
// Screenshot analysis — the full presigned-URL flow.
//
// 1. request a presigned PUT URL for the file's content type
// 2. upload the file bytes directly to S3
// 3. run the OCR + classification pipeline against the resulting key
//
// Each step surfaces its own error so the UI can show a calm, specific message
// instead of a generic "analysis failed" banner.
// --------------------------------------------------------------------------- #

export function useAnalyzeScreenshot() {
  return useMutation<AnalysisResponse, Error, File>({
    mutationFn: async (file) => {
      const contentType =
        file.type === 'image/jpeg' ? 'image/jpeg' : 'image/png';
      const presigned = await getPresignedUploadUrl(contentType);
      await uploadToS3(presigned, file);
      return analyzeScreenshot(presigned.s3_key);
    },
  });
}

// --------------------------------------------------------------------------- #
// Entity lookup
// --------------------------------------------------------------------------- #

export function useEntityHistory(value: string, enabled: boolean) {
  return useQuery<EntityHistoryResponse, Error>({
    queryKey: queryKeys.entity(value),
    queryFn: () => getEntityHistory(value),
    enabled,
  });
}