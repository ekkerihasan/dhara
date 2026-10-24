"""Offline checks for the city housing benchmark, without model credentials."""

import unittest

from server.env import DharaAiEnvironment
from server.models import ContractAction
from server.scenarios import get_scenario


class LeaseEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.env = DharaAiEnvironment()
        self.observation = self.env.reset(task_name="residential_lease")

    def act(self, action_type, **kwargs):
        return self.env.step(ContractAction(action_type=action_type, **kwargs))

    def test_initial_observation_does_not_expose_grader_fields(self):
        serialized = self.observation.model_dump_json()
        for private in ("has_issue", "ideal_revision", "grading_rules", "correct_agent_response"):
            self.assertNotIn(private, serialized)
        self.assertEqual(len(self.observation.clauses), 6)

    def test_clarification_returns_facts_for_clean_and_issue_clauses(self):
        for clause_id in ("clause_1", "clause_2"):
            obs = self.act("request_clarification", clause_id=clause_id, question="Where is the property and which rules apply?")
            self.assertIn("Karnataka", obs.last_action_result)
            self.assertIn("not been verified", obs.last_action_result)
            self.assertNotIn("Concern raised", obs.last_action_result)
            self.assertNotIn("standard and satisfies", obs.last_action_result)

    def test_complete_preference_review_scores_one(self):
        scenario = get_scenario("residential_lease")
        for clause in scenario.clauses:
            if not clause.has_issue:
                self.act("accept_clause", clause_id=clause.id)
                continue
            self.act("flag_issue", clause_id=clause.id, issue="Conflicts with stated client preferences.")
            obs = self.act("suggest_revision", clause_id=clause.id, revised_text=clause.ideal_revision)
            if clause.id == "clause_2":
                self.assertEqual(self.env.state.clauses[clause.id].status, "negotiating")
                self.act("suggest_revision", clause_id=clause.id, revised_text=clause.ideal_revision + " This is the tenant's final proposal.")
            elif clause.id == "clause_3":
                self.act("accept_clause", clause_id=clause.id)
        obs = self.act("submit_review")
        self.assertTrue(obs.done)
        self.assertAlmostEqual(self.env.state.accumulated_reward, 1.0)

    def test_repeated_revision_is_bounded_without_reward(self):
        self.act("flag_issue", clause_id="clause_2", issue="Deposit exceeds my budget")
        text = get_scenario("residential_lease").clauses[1].ideal_revision
        self.act("suggest_revision", clause_id="clause_2", revised_text=text)
        obs = self.act("suggest_revision", clause_id="clause_2", revised_text=text)
        self.assertIn("Repeated revision", obs.last_action_error)
        self.assertEqual(obs.reward, 0)

    def test_step_budget_terminates_even_on_invalid_actions(self):
        for _ in range(22):
            obs = self.act("accept_clause", clause_id="missing")
        self.assertTrue(obs.done)
        self.assertEqual(obs.steps_remaining, 0)

    def test_distinct_revisions_are_capped(self):
        self.act("flag_issue", clause_id="clause_4", issue="Entry notice missing")
        for number in range(3):
            self.act("suggest_revision", clause_id="clause_4", revised_text=f"Proposal {number}: give 24 hours written notice.")
        obs = self.act("suggest_revision", clause_id="clause_4", revised_text="Fourth proposal")
        self.assertIn("Revision limit", obs.last_action_error)
        self.assertEqual(len(self.env.state.clauses["clause_4"].revisions), 3)

    def test_repeated_revision_ignores_case_and_whitespace(self):
        self.act("flag_issue", clause_id="clause_4", issue="Entry notice missing")
        self.act("suggest_revision", clause_id="clause_4", revised_text="Give 24 hours written notice.")
        obs = self.act("suggest_revision", clause_id="clause_4", revised_text="  GIVE  24 hours\nwritten NOTICE.  ")
        self.assertIn("Repeated revision", obs.last_action_error)
        self.assertEqual(len(self.env.state.clauses["clause_4"].revisions), 1)

    def test_existing_scenarios_still_reset(self):
        for task, count in (("nda", 5), ("saas", 7), ("jv", 10)):
            self.assertEqual(len(self.env.reset(task_name=task).clauses), count)


if __name__ == "__main__":
    unittest.main()
