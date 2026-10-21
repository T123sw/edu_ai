"""Explicitly publish saved resources of one stopped preparation, without generation.

Run with the backend's DATABASE_URL and storage environment after deploying the
progressive delivery reader. Prints only the public delivery receipt.
"""
import argparse
import json

from sqlalchemy import select
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('preparation_id')
    args = parser.parse_args()
    from app.course_preparation.dependencies import engine
    from app.course_preparation.authorizer import PreparationReferenceAuthorizer
    from app.course_preparation.adapters.document_store import DocumentStore
    from app.course_preparation.adapters.documents import PersonalDocumentReader
    from app.course_preparation.adapters.targets import TargetStore
    from app.course_preparation.lifecycle_repository import LifecycleRepository
    from app.course_preparation.progressive_delivery import ProgressiveDelivery
    from app.services.personal_knowledge_service import PersonalKnowledgeService
    from app.database.models import CoursePreparationRecord
    db = engine()
    documents = DocumentStore(db, PersonalDocumentReader(PersonalKnowledgeService()))
    repository = LifecycleRepository(db, authorizer=PreparationReferenceAuthorizer(db, documents, targets=TargetStore(db)),
                                     retry_only=True)
    with Session(db) as session:
        owner = session.scalar(select(CoursePreparationRecord.owner_user_id).where(
            CoursePreparationRecord.preparation_id == args.preparation_id))
        if owner is None:
            raise SystemExit('Preparation not found')
    result = ProgressiveDelivery(repository).recover_saved(owner, args.preparation_id)
    print(json.dumps({'preparation_id': args.preparation_id, 'status': result['status'],
                      'result_ref': result['result_ref'], 'failure': result['failure']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
