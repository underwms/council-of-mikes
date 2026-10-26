"""LangChain callbacks capture node boundaries without changing graph flow."""
import os

from langchain_core.callbacks import BaseCallbackHandler

from council.narration import NarrationQueue, narration_context


class NodeNarrationCapture(BaseCallbackHandler):
    run_inline = True
    raise_error = False

    def __init__(self, context, session):
        self.context, self.session = context, session
        self.visits = {}
        self.active = {}
        self.queue = None
        self.launches = 0

    def on_chain_start(self, serialized, inputs, *, run_id, **kwargs):
        name = kwargs.get('name')
        metadata = kwargs.get('metadata') or {}
        if not self.session or metadata.get('langgraph_node') != name:
            return
        from council.diagnostics import _STAGES
        if name not in _STAGES or not isinstance(inputs, dict) or not inputs.get('model_configuration'):
            return
        if os.environ.get('COUNCIL_NARRATION_ENABLED', '1') != '1':
            return
        try:
            process = getattr(self.session, '_narrator', None)
            dead = process is not None and callable(getattr(process, 'poll', None)) and process.poll() is not None
            if self.queue is None or dead:
                if self.session.observations_status != 'available' or self.session.finished:
                    return
                if self.launches >= 3:
                    return
                from council.narration_worker import start_narrator
                self.launches += 1
                self.queue = NarrationQueue(self.session.observations.db)
                self.session._narrator = start_narrator(self.context, inputs['model_configuration'],
                                                       self.session.run_id, self.session.session_id)
                self.session._narration_observer = self.observe
            safe = narration_context(inputs, name)
            self.active[name] = safe
            self.visits[run_id] = (name, safe)
        except Exception:
            # Observation failures must not propagate into node execution.
            self.queue = None

    def observe(self, event, record, seq):
        stage = record['stage']
        if stage == 'model':
            # Match model operations to their enclosing stage when there is one active node.
            if len(self.active) != 1:
                return
            stage = next(iter(self.active))
        if stage not in self.active:
            return
        if event not in {'node_finished', 'delivery_state'}:
            self.queue.enqueue(self.session.run_id, self.session.session_id, seq, self.active[stage])

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        visit = self.visits.pop(run_id, None)
        if not visit or self.session.finished or self.queue is None:
            return
        stage, before = visit
        try:
            after = narration_context(outputs, stage) if isinstance(outputs, dict) else before
            for key in ('task', 'task_kind', 'phase'):
                if key in before:
                    after[key] = before[key]
            source = self.session.observations.db.execute(
                "SELECT source_seq FROM observation_events WHERE run_id=? AND session_id=? AND json_extract(payload,'$.stage')=? "
                "AND event IN ('node_finished','node_failed','delivery_state','approval_waiting','planning_blocked') ORDER BY source_seq DESC LIMIT 1",
                (self.session.run_id, self.session.session_id, stage)).fetchone()
            if source:
                self.queue.enqueue(self.session.run_id, self.session.session_id, source[0], after)
        except Exception:
            pass
        finally:
            self.active.pop(stage, None)

    def on_chain_error(self, error, *, run_id, **kwargs):
        self.on_chain_end({}, run_id=run_id)
