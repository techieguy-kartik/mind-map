import json

from server import db,registry


def test_catalog_migration_preserves_local_identity_and_user_changes(tmp_path,monkeypatch):
    monkeypatch.setenv('ATLAS_DB',str(tmp_path/'registry.sqlite3'))
    path=tmp_path/'catalog.json'
    monkeypatch.setattr(registry,'CATALOG_PATH',path)
    db.initialize()
    original=db.get('entity','tesla')
    original['description']='User-maintained notes'
    db.put('entity',original)
    candidate={**original,'id':'wd-q478214','wikidata_id':'Q478214','description':'Imported text',
               'sectors':['Automotive & Mobility'],'source_url':'https://www.wikidata.org/wiki/Q478214'}
    path.write_text(json.dumps({'companies':[candidate]}))
    db.initialize(recover_jobs=False)
    db.initialize(recover_jobs=False)
    saved=db.get('entity','tesla')
    assert saved['description']=='User-maintained notes'
    assert saved['wikidata_id']=='Q478214'
    assert 'Automotive & Mobility' in saved['sectors']
    assert db.get('entity','wd-q478214') is None
    with db.connect() as connection:
        assert connection.execute("SELECT 1 FROM watchlist WHERE entity_id='jio'").fetchone()


def test_change_cursor_can_resume_after_a_write(tmp_path,monkeypatch):
    monkeypatch.setenv('ATLAS_DB',str(tmp_path/'changes.sqlite3'))
    db.initialize()
    cursor=db.change_cursor()
    db.put('source_run',{'id':'test','status':'Healthy'})
    changes=db.changes_since(cursor)
    assert len(changes)==1
    assert changes[0]['kind']=='source_run'
    assert db.changes_since(changes[0]['seq'])==[]
