from fastapi import HTTPException
from psycopg.types.json import Jsonb

from .db import event
from .fieldbook import one


def misrecord(db, sample_id, reason, actor):
    sample = one(db, '''
        SELECT s.id,s.observed_day,s.slot,b.code AS block_code
        FROM microclimate_sample s JOIN vine_block b ON b.id=s.block_id WHERE s.id=%s
    ''', (sample_id,), '采样读数')
    if db.execute('SELECT 1 FROM sample_misrecord WHERE sample_id=%s', (sample_id,)).fetchone():
        raise HTTPException(409, '该读数已标记错录，撤回记录保持不变')
    db.execute('INSERT INTO sample_misrecord(sample_id,reason,actor) VALUES (%s,%s,%s)',
               (sample_id, reason, actor))
    cause = dict(sample_id=sample_id, block=sample['block_code'], day=sample['observed_day'].isoformat(),
                 slot=sample['slot'], reason=reason)
    runs = db.execute('''
        SELECT r.id,r.status FROM climate_run r
        WHERE r.status IN ('queued','review','effective')
          AND EXISTS (
              SELECT 1 FROM jsonb_array_elements(r.snapshot) AS b
              CROSS JOIN jsonb_array_elements(b->'readings') AS rd
              WHERE (rd->>'id')::int = %s
          ) ORDER BY r.id
    ''', (sample_id,)).fetchall()
    for run in runs:
        db.execute("UPDATE climate_label SET state='recalled' WHERE run_id=%s", (run['id'],))
        db.execute("UPDATE climate_run SET status='recalled',recall=%s WHERE id=%s",
                   (Jsonb(dict(cause, actor=actor)), run['id']))
    reverted = db.execute('''
        UPDATE climate_label l SET state='active'
        FROM (
            SELECT DISTINCT ON (block_id) id,block_id FROM climate_label
            WHERE state='superseded' ORDER BY block_id,revision DESC
        ) t
        WHERE l.id=t.id
          AND NOT EXISTS (SELECT 1 FROM climate_label a WHERE a.block_id=t.block_id AND a.state='active')
        RETURNING l.block_id,l.profile,l.revision
    ''').fetchall()
    moved = db.execute('''
        UPDATE irrigation_round r SET state='needs_replan'
        FROM climate_label l
        WHERE r.label_id=l.id AND l.state='recalled' AND r.state='scheduled'
        RETURNING r.id,r.code
    ''').fetchall()
    event(db, actor, 'sample_misrecorded', sample_id, **cause,
          recalled_runs=[run['id'] for run in runs],
          reverted_labels=[dict(item) for item in reverted],
          replan_rounds=[item['code'] for item in moved])
    return {'sample_id': sample_id, 'recalled_runs': [run['id'] for run in runs],
            'reverted_labels': reverted, 'replan_rounds': moved}
