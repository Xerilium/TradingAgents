import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import math
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, data):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def check(row):
    if hashlib.sha256(row['text'].encode('utf-8')).hexdigest() != row['text_sha256']:
        raise ValueError('Post text does not match its saved hash')


def reviewed(row):
    review = row['review']
    if review['status'] not in ('unreviewed', 'ambiguous', 'reviewed'):
        raise ValueError('Invalid review status')
    if review['status'] != 'reviewed':
        return False
    if not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
        raise ValueError('Reviewed posts require a reviewer')
    try:
        date.fromisoformat(review.get('date', ''))
    except (TypeError, ValueError):
        raise ValueError('Reviewed posts require an ISO date') from None
    if type(review.get('about')) is not bool or review.get('stance') not in ('bullish', 'bearish', 'neutral'):
        raise ValueError('Reviewed posts require independent about and stance labels')
    return True


def bound(row):
    model = row.get('model_identity')
    policy, questions = row.get('decision_policy'), row.get('questions')
    if not (row.get('status') == 'classified' and isinstance(policy, dict)
            and isinstance(policy.get('version'), str) and bool(policy['version'])
            and all(type(policy.get(k)) in (int, float) and math.isfinite(policy[k]) and 0 <= policy[k] <= 1
                    for k in ('relevance_threshold', 'stance_threshold'))
            and type(policy.get('stance_requires_unique_winner')) is bool
            and type(policy.get('calibrated')) is bool
            and isinstance(model, dict) and all(isinstance(model.get(k), str) and bool(model[k])
                                                for k in ('model', 'revision', 'package'))
            and isinstance(row.get('model_alias'), str) and bool(row['model_alias'])
            and isinstance(questions, dict) and set(questions) == {'about', 'stance'}
            and all(isinstance(q, dict) for q in questions.values())
            and questions['about'].get('type') == 'noul' and questions['stance'].get('type') == 'choice'
            and all(isinstance(q.get('instructions'), str) and q['instructions'].strip() for q in questions.values())
            and all(isinstance(q.get('criteria'), dict) for q in questions.values())
            and set(questions['about']['criteria']) == {'true', 'false'}
            and set(questions['stance']['criteria']) == {'bullish', 'bearish', 'neutral'}
            and all(isinstance(v, str) and v.strip() for q in questions.values() for v in q['criteria'].values())):
        return False
    encoded = json.dumps(questions, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return row.get('questions_sha256') == hashlib.sha256(encoded).hexdigest()


def export(run):
    if not run.get('id') or not isinstance(run.get('results'), list):
        raise ValueError('Expected saved /api/runs/<id> JSON with id and results')
    rows = []
    for result in run['results']:
        for source, evidence in (result.get('social_sentiment', {}).get('sources') or {}).items():
            for index, post in enumerate(evidence.get('posts', [])):
                output = post.get('result') or {}
                inference = output.get('inference') or {}
                row = {'run_id': run['id'], 'symbol': result.get('symbol'), 'source': source,
                       'index': index, 'text': post['text'], 'text_sha256': post['text_sha256'],
                       'status': post.get('status'), 'questions': inference.get('questions'),
                       'questions_sha256': inference.get('questions_sha256'),
                       'model_alias': post.get('model', evidence.get('model')),
                       'decision_policy': evidence.get('decision_policy'), 'model_identity': output.get('model_identity'),
                       'prediction': {'relevance': post.get('relevance_prediction'), 'relevance_uncertain': post.get('relevance_uncertain'), 'stance': post.get('stance'),
                                      'raw_stance': post.get('raw_prediction'), 'raw_result': output.get('raw_result')},
                       'review': {'status': 'unreviewed', 'reviewer': '', 'date': '',
                                  'about': None, 'stance': None, 'notes': ''}}
                check(row)
                rows.append(row)
    return {'format': 'laya-human-review-v1', 'rows': rows}


def main():
    parser = argparse.ArgumentParser(description='Review saved Laya decisions without inference')
    parser.add_argument('command', choices=('export', 'report', 'sdk'))
    parser.add_argument('input')
    parser.add_argument('output', help='New output file; never overwritten')
    parser.add_argument('--source', help='Original saved run JSON, required for report and sdk')
    args = parser.parse_args()
    data = load(args.input)
    if args.command == 'export':
        packet = export(data)
        packet['source_sha256'] = hashlib.sha256(Path(args.input).read_bytes()).hexdigest()
        save(args.output, packet)
        print(json.dumps({'unreviewed': len(packet['rows'])}))
        return
    if data.get('format') != 'laya-human-review-v1' or not isinstance(data.get('rows'), list):
        raise ValueError('Expected a human review packet')
    if not args.source:
        parser.error('--source is required for report and sdk')
    if hashlib.sha256(Path(args.source).read_bytes()).hexdigest() != data.get('source_sha256'):
        raise ValueError('Original run file differs from the exported source')
    originals = export(load(args.source))['rows']
    if len(originals) != len(data['rows']):
        raise ValueError('Review packet does not match original run')
    counts, groups, sdk = Counter(), {}, []
    for row, original in zip(data['rows'], originals, strict=True):
        core = {key: value for key, value in row.items() if key != 'review'}
        original_core = {key: value for key, value in original.items() if key != 'review'}
        if core != original_core:
            raise ValueError('Review packet evidence differs from original run')
        check(row)
        if not reviewed(row):
            counts[row['review']['status']] += 1
            continue
        if not bound(row):
            counts['reviewed_without_bound_prediction'] += 1
            continue
        prediction, review = row['prediction'], row['review']
        if prediction.get('relevance') not in ('off_topic', 'retained') or prediction.get('stance') not in ('bullish', 'bearish', 'neutral', 'unclear'):
            counts['reviewed_invalid_prediction'] += 1
            continue
        questions = row.get('questions')
        question_bytes = json.dumps(questions, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        binding = {'policy': row['decision_policy'], 'model_identity': row['model_identity'],
                   'model_alias': row['model_alias'], 'questions_sha256': hashlib.sha256(question_bytes).hexdigest()}
        key = json.dumps(binding, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        group = groups.setdefault(key, {'binding': binding, 'count': 0, 'relevance': Counter(), 'stance': Counter()})
        group['count'] += 1
        relevance_label = "uncertain" if prediction.get("relevance_uncertain") else prediction["relevance"]
        group['relevance'][f"{review['about']} -> {relevance_label}"] += 1
        group['stance'][f"{review['stance']} -> {prediction['stance']}"] += 1
        counts['reviewed_with_prediction'] += 1
        sdk.append({'state': row['text'], 'questions': questions,
                    'expected': {'about': review['about'], 'stance': review['stance']},
                    'tags': [row['source'], row['symbol']], 'model': row['model_alias']})
    if args.command == 'report':
        save(args.output, {'total': len(data['rows']), 'counts': dict(counts),
                           'groups': list(groups.values()),
                           'note': 'Saved policy outputs; unclear is not neutral. No inference was run.'})
    else:
        with Path(args.output).open('x', encoding='utf-8') as f:
            for row in sdk:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(json.dumps({'exported': len(sdk), 'counts': dict(counts)}))


if __name__ == '__main__':
    main()
