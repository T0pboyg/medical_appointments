import unittest
from unittest.mock import patch

from assistant_knowledge import retrieve
from assistant_service import answer_question


class RetrievalTests(unittest.TestCase):
    def test_bringing_question_returns_only_relevant_section(self):
        documents = retrieve('Τι πρέπει να φέρω μαζί μου στον γιατρό;')
        self.assertEqual(documents[0]['id'], 'visit-preparation')
        self.assertIn('λίστα των φαρμάκων', documents[0]['text'])
        self.assertNotIn('βάλτε πρώτα', documents[0]['text'])
        self.assertNotIn('επεμβάσεις', documents[0]['text'])

    def test_questions_to_discuss_selects_discussion_section(self):
        documents = retrieve('Τι να συζητήσω στην επίσκεψη στον γιατρό;')
        self.assertTrue(documents)
        self.assertIn('σημαντικότερα', documents[0]['text'])
        self.assertNotIn('συμπληρωμάτων', documents[0]['text'])

    def test_fasting_question_keeps_preparation_caveat(self):
        documents = retrieve('Πρέπει να είμαι νηστικός πριν την αιμοληψία;')
        self.assertIn('Δεν απαιτούν όλες', documents[0]['text'])
        self.assertNotIn('ιατρικό ιστορικό', documents[0]['text'])

    def test_visit_preparation_phrases(self):
        for question in (
            'Τι χαρτιά να φέρω στον γιατρό;',
            'Πώς να ετοιμαστώ πριν την επίσκεψη;',
            'Τι να πάρω μαζί στο ραντεβού;',
            'ΠΡΟΕΤΟΙΜΑΣΙΑ ΓΙΑ ΕΠΙΣΚΕΨΗ',
            'Τι να φέρω στον γιατρό; Χρειάζομαι τις εξετάσεις μου;',
        ):
            with self.subTest(question=question):
                self.assertEqual(retrieve(question)[0]['id'], 'visit-preparation')

    def test_lab_preparation_phrases(self):
        for question in (
            'Πώς να προετοιμαστώ για εξετάσεις αίματος;',
            'Πρέπει να είμαι νηστικός πριν την αιμοληψία;',
            'Μπορώ να φάω πριν την εξέταση;',
            'Τι προετοιμασία χρειάζεται για εργαστηριακό έλεγχο;',
            'ΝΗΣΤΕΙΑ ΠΡΙΝ ΤΙΣ ΕΞΕΤΑΣΕΙΣ',
        ):
            with self.subTest(question=question):
                self.assertEqual(retrieve(question)[0]['id'], 'lab-preparation')

    def test_general_results_phrases(self):
        for question in (
            'Τι σημαίνουν γενικά οι τιμές αναφοράς;',
            'Πώς ερμηνεύονται γενικά τα αποτελέσματα εξετάσεων;',
            'Τι σημαίνει φυσιολογικό εύρος σε εργαστηριακή εξέταση;',
        ):
            with self.subTest(question=question):
                self.assertEqual(retrieve(question)[0]['id'], 'lab-results')

    def test_generic_and_unsupported_questions_abstain(self):
        for question in (
            'γιατρός', 'εξετάσεις', 'νερό', 'εργαστήριο',
            'Πότε έχει ραντεβού;', 'Θέλω να κλείσω ραντεβού',
            'Πόσο κοστίζει η επίσκεψη;', 'Ποιο είναι το ωράριο;',
            'Ποιος είναι ο καλύτερος γιατρός;',
            'Πώς να ετοιμαστώ για συνέντευξη;',
        ):
            with self.subTest(question=question):
                self.assertEqual(retrieve(question), [])

    def test_punctuation_accents_and_spacing_do_not_change_ranking(self):
        self.assertEqual(
            [d['id'] for d in retrieve('ΠΩΣ να ετοιμαστώ, πριν την επίσκεψη;')],
            [d['id'] for d in retrieve('πως  να ετοιμαστω πριν την επισκεψη')],
        )


class RetrievalServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_medication_advice_still_abstains(self):
        for question in (
            'Τι φάρμακο να πάρω για πονοκέφαλο;',
            'Τι δοσολογία να πάρω;',
            'Η εξέταση έδειξε 150, τι έχω;',
        ):
            with self.subTest(question=question):
                with patch('assistant_service.httpx.AsyncClient', side_effect=AssertionError('Unexpected model request')):
                    result = await answer_question(question)
                if question == 'Τι φάρμακο να πάρω για πονοκέφαλο;':
                    # Headache now has a bounded educational pathway, but it
                    # must explicitly refuse medication selection/dosing.
                    self.assertEqual(result['status'], 'symptom_information')
                    self.assertIn('Δεν μπορώ να επιλέξω φάρμακο ή δοσολογία', result['answer'])
                    self.assertNotIn('mg', result['answer'])
                else:
                    self.assertEqual(result['status'], 'insufficient')

    async def test_take_with_me_is_not_mistaken_for_medication_advice(self):
        import httpx
        async def respond(request):
            return httpx.Response(200, json={
                'done_reason': 'stop',
                'message': {'content': '{"selected_ids":["visit-preparation"]}'},
            })
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            result = await answer_question('Τι να πάρω μαζί μου στον γιατρό;', client)
        self.assertEqual(result['status'], 'grounded')
        self.assertIn('λίστα των φαρμάκων', result['answer'])

    async def test_no_model_request_for_generic_word(self):
        with patch('assistant_service.httpx.AsyncClient', side_effect=AssertionError('Unexpected model request')) as client:
            result = await answer_question('γιατρός')
        self.assertEqual(result['status'], 'insufficient')
        client.assert_not_called()
