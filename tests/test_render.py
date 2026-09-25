import unittest

class TestRenderLayout(unittest.TestCase):
    def test_layout_footer_at_bottom_outside_body_frames(self):
        # We wish to import layout from scripts.switcher.render
        from scripts.switcher.render import compute_layout

        width = 120
        height = 30
        layout = compute_layout(width, height, preview_pct=50, show_preview=True)

        # Footer must be at height - 2 (or bottom line inside border / full width at bottom)
        # Spec says:
        # "Outer border/title, full-width top mode/input line, split body with session list and preview,
        # full-width final single help line OUTSIDE both body boxes; divider ends ABOVE help."
        # If terminal height is 30:
        # y=0: top mode/input line or top border/title
        # Let's inspect layout coordinates:
        self.assertEqual(layout.total_w, 120)
        self.assertEqual(layout.total_h, 30)

        # Help line is at y = height - 2 (with outer border at height - 1)
        # Help line full width spans inner width
        self.assertEqual(layout.help_y, 28)
        self.assertEqual(layout.help_x, 1)
        self.assertEqual(layout.help_w, 118)

        # Body must end strictly ABOVE help line
        self.assertLess(layout.body_bottom_y, layout.help_y)
        self.assertEqual(layout.body_bottom_y, 27)

        # Split body: list on left, preview on right, divider ending above help
        self.assertGreater(layout.preview_w, 0)
        self.assertGreater(layout.list_w, 0)
        self.assertEqual(layout.divider_bottom_y, layout.body_bottom_y)

if __name__ == '__main__':
    unittest.main()
