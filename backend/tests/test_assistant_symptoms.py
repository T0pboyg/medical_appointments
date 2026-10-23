import unittest
from unittest.mock import patch

from assistant_service import answer_question


class SymptomInformationTests(unittest.IsolatedAsyncioTestCase):
    async def test_additional_common_symptoms(self):
        for question, source_id in (
            ('Έχω πονοκέφαλο', 'headache-original'),
            ('Έχω βήχα', 'cough-original'),
            ('Έχω διάρροια και κάνω εμετό', 'diarrhoea-vomiting-original'),
        ):
            with self.subTest(question=question):
                with patch('assistant_service.httpx.AsyncClient', side_effect=AssertionError('No clinical LLM call')):
                    answer = await answer_question(question)
                self.assertEqual(answer['status'], 'symptom_information')
                self.assertIn(source_id, [s['id'] for s in answer['sources']])
                self.assertIn('ενήλικες', answer['answer'])
                self.assertIn('112', answer['answer'])

    async def test_additional_danger_signs(self):
        for question in (
            'Ξαφνικός πολύ δυνατός πονοκέφαλος',
            'Πονοκέφαλος και δυσκολία στην ομιλία',
            'Πυρετός, πονοκέφαλος και δυσκαμψία αυχένα',
            'Κάνω εμετό με αίμα',
            'Έχω πράσινο εμετό',
            'Διάρροια και ξαφνικός έντονος πόνος στην κοιλιά',
        ):
            with self.subTest(question=question):
                answer = await answer_question(question)
                self.assertEqual(answer['status'], 'urgent')
                self.assertIn('112', answer['answer'])
                self.assertFalse(answer.get('actions'))

    async def test_new_symptoms_keep_special_population_boundary(self):
        for question in ('Το παιδί έχει βήχα', 'Είμαι έγκυος και έχω πονοκέφαλο', 'Είμαι 14 ετών και κάνω εμετό'):
            with self.subTest(question=question):
                answer = await answer_question(question)
                self.assertEqual(answer['status'], 'symptom_scope')

    async def test_multiple_symptoms_keep_relevant_sources(self):
        answer = await answer_question('Έχω βήχα και πυρετό')
        self.assertIn('cough-original', [s['id'] for s in answer['sources']])
        self.assertIn('adult-fever-original', [s['id'] for s in answer['sources']])

    async def test_persistent_and_dehydration_warnings_present(self):
        answer = await answer_question('Έχω διάρροια')
        self.assertIn('υγρά', answer['answer'])
        self.assertIn('αφυδάτωσ', answer['answer'])
        self.assertIn('γιατρό', answer['answer'])

    async def test_fever_and_sore_throat_give_bounded_information(self):
        with patch('assistant_service.httpx.AsyncClient', side_effect=AssertionError('No clinical model call')):
            answer = await answer_question('έχω υψηλό πυρετό και πονόλαιμο')
        self.assertEqual(answer['status'], 'symptom_information')
        self.assertIn('ενήλικες', answer['answer'])
        self.assertIn('γιατρό', answer['answer'])
        self.assertIn('112', answer['answer'])
        self.assertNotIn('booking_form', str(answer.get('actions', [])))
        self.assertEqual(len(answer['sources']), 2)

    async def test_emergency_signs_take_priority_over_booking(self):
        for message in (
            'Πονόλαιμος και δεν μπορώ να καταπιώ, θέλω ραντεβού',
            'Έχω πυρετό και δυσκολία στην αναπνοή',
            'Πονόλαιμος, τρέχουν σάλια και δεν μπορώ να τα καταπιώ',
            'Έχω πυρετό και πόνο στο στήθος',
            'Πυρετός και δεν μπορώ να αναπνεύσω, κλείσε ραντεβού',
        ):
            with self.subTest(message=message):
                answer = await answer_question(message)
                self.assertEqual(answer['status'], 'urgent')
                self.assertIn('112', answer['answer'])
                self.assertFalse(answer.get('actions'))

    async def test_children_and_pregnancy_not_given_adult_self_care(self):
        for message in ('Το παιδί μου έχει πυρετό', 'Είμαι έγκυος και έχω πονόλαιμο', 'Το μωρό έχει πυρετό', 'Είμαι 15 ετών και έχω πυρετό'):
            with self.subTest(message=message):
                answer = await answer_question(message)
                self.assertEqual(answer['status'], 'symptom_scope')
                self.assertIn('γιατρό', answer['answer'])

    async def test_dosage_request_does_not_produce_dose(self):
        answer = await answer_question('Έχω πυρετό 39, πόσα mg αντιβίωση να πάρω;')
        self.assertEqual(answer['status'], 'symptom_information')
        self.assertIn('δοσολογ', answer['answer'])
        self.assertNotIn('39', answer['answer'])

    async def test_negated_red_flag_never_gives_all_clear(self):
        answer = await answer_question('Έχω πυρετό αλλά δεν έχω δυσκολία στην αναπνοή')
        self.assertIn('112', answer['answer'])
        self.assertNotIn('δεν χρειάζεται', answer['answer'])

    async def test_high_risk_scope(self):
        answer = await answer_question('Έχω ανοσοκαταστολή και πονόλαιμο')
        self.assertEqual(answer['status'], 'symptom_scope')

    async def test_supported_symptom_does_not_route_to_normal_booking(self):
        answer = await answer_question('Έχω υψηλό πυρετό και θέλω να κλείσω ραντεβού')
        self.assertEqual(answer['status'], 'symptom_information')
        self.assertFalse(answer.get('actions'))
