-- Voice notes: Sarvam speech-to-text drafts that the customer reviews like OCR.
ALTER TABLE evidence DROP CONSTRAINT evidence_type_check;
ALTER TABLE evidence ADD CHECK (type IN ('message','call_summary','screenshot','voice_note'));
ALTER TABLE evidence DROP CONSTRAINT evidence_check2;
ALTER TABLE evidence ADD CHECK (type IN ('screenshot','voice_note') OR review_state = 'confirmed');
