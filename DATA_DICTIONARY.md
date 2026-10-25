# Companion data dictionary

Use this field map beside the reader draft’s 25-term glossary. Field names are
local to each chapter’s schema; the companion preserves the original APIs. The
common fixture is a continuity example, not a promise that every chapter has
identical contracts or every extension belongs to the same history.

| Concept | Fields or names in the labs | Meaning and constraint |
| --- | --- | --- |
| Entity | customer_id; customer in Chapter 4; entity in Chapters 5–6 | The customer described by the feature. C1 is the common source customer; it is not an event or request ID. |
| Business event | event_id; event in Chapter 4; source_event_id in Chapter 6 | One order. Foundations uses globally unique event IDs; some older standalone adapters namespace event IDs by customer/entity. The shared fixture is unique under both. |
| Source revision | revision; version in Chapters 4–5 | A positive revision number for one business event. Select the greatest eligible revision, not the last delivery. It is not an output revision. |
| Source amount and operation | amount; op in foundations | Nonnegative integer units for an upsert. A foundation tombstone has op=delete and amount=None. Chapter 10's serving adapter rejects tombstones and restoration. |
| Event time | event_time; occurred_at for outcomes | When the activity happened. Feature membership and label membership use their own explicit intervals. |
| Source availability | available_at | When this source version became usable by the reference calculation. Retries preserve it. It does not imply downstream store or cache visibility. |
| Delivery observation | delivery_id; delivered_at in foundations; at in Chapter 5 | One recorded transport observation. Replaying it preserves its identity; a distinct attempt receives another delivery identity. |
| Decision | decision_id/decision_time in Chapter 4; decision_id/decision_at in Chapter 7; row_id/decision_at in Chapter 10 | One original request whose historical feature uses its own information cutoff. Different decisions can share an entity. |
| Knowledge cutoff | known_at; cutoff; source_cutoff; input_cutoff | Inclusive boundary for availability. Keep the associated event window fixed when performing a corrected view. |
| History coverage | history_known; history_complete in Chapter 4; SourceHistory.known in Chapter 6 | Explicit assertion about the required usable source history for an entity, window and cutoff. Known empty yields 0; unknown yields None where supported. Chapter 5 rejects unknown coverage. |
| Rolling definition | known_spend_60m_v1 | Use [decision−60,decision) and availability at or before that decision. Retain the definition with the row. |
| Backfill definition | spend_before_decision plus window_minutes, mode, corrected_cutoff | Chapter 7's full definition object expresses the historical 60-minute contract only when all those parameters match. The family name alone is not a feature identity. |
| Fixed feature cell | known_spend_fixed_window_v1 plus policy, entity, window_start, window_end | The serving cell is keyed by all five semantic fields. [540,600) stays fixed when later requests arrive. |
| Published state | output revision; emitted_at or published_at; contributions or source_versions | One complete replacement of a feature cell and its source provenance. It must not be added to previous full values. |
| Store and cache clocks | visible_at; cache snapshot or refresh time; request time | Separate downstream boundaries. In Chapters 6 and 9, same-minute order is publication, store visibility, cache refresh, then request. |
| Label eligibility | finalized_at; label_cutoff; FIT_TIME; EXTRACT_TIME | Chapter 4 labels become usable only after the full (decision,decision+120] horizon is certified complete. Training requires maturity at fit time; validation labels can mature by extraction. |
| Serving evidence | raw_value; feature_missing; fallback_used; model_input | Preserve the observed lookup, missing state, fallback action and final model input separately. A fallback zero is not a known zero-spend history. |
| Retained artifact identity | manifest; dataset identity; digest; runtime; implementation files | Binds the intended inputs, semantic definition, implementation, environment and outputs. Retain actual bytes; a digest cannot reconstruct or authenticate them by itself. |

For exact local types and validation rules, see the corresponding chapter
README and source module. The fixed [540,600) cell and a rolling decision window
are separate contracts; customer C1, event C revision 1 and decision D1 are
different identities even when their names look similar.
