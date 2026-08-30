"""Debug: test individual vs batch mount."""
import asyncio

from textual.app import App, ComposeResult
from textual.widgets import Label, ListItem, ListView


class TestApp(App):
    def compose(self) -> ComposeResult:
        yield ListView()


async def main():
    app = TestApp()
    async with app.run_test() as pilot:
        lv = app.query_one(ListView)
        
        # Create and mount items
        for i in range(5):
            await lv.mount(ListItem(Label(f"Song {i}")))
        await pilot.pause(0.1)
        
        print(f"Before: {len(lv.children)} items, first has {len(lv.children[0].children)} children")
        
        # Remove
        await lv.remove_children()
        await pilot.pause(0.1)
        await asyncio.sleep(0)
        
        # Create new items
        new_items = [ListItem(Label(f"New Song {i}")) for i in range(3)]
        print(f"Created {len(new_items)} items")
        for i, item in enumerate(new_items):
            print(f"  Item {i} before mount: children={list(item.children)}")
        
        # Mount individually (not batch)
        for item in new_items:
            await lv.mount(item)
            print(f"  After individual mount: item.children={list(item.children)}")
        
        await pilot.pause(0.1)
        print(f"\nFinal: {len(lv.children)} items")
        for i, child in enumerate(lv.children):
            print(f"  Item {i}: children={list(child.children)}")


if __name__ == "__main__":
    asyncio.run(main())
