from django.test import SimpleTestCase

from builder.services.error_fixer import ErrorFixer


class ErrorFixerNormalizationTestCase(SimpleTestCase):
    def test_placeholder_fix_target_is_replaced_with_preferred_file(self):
        fixer = ErrorFixer()

        fix_data = fixer._normalize_fix_data(
            {
                "explanation": "Update the failing file.",
                "fixed_code": "export default function App(){ return null; }",
                "files_to_update": ["file.js"],
            },
            "src/App.jsx",
        )

        self.assertEqual(fix_data["files_to_update"], ["src/app.jsx"])
