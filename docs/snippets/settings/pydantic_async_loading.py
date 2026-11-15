# pyright: reportUndefinedVariable=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
import anyio


async def main() -> None:
    settings = await Settings.load()
    print(settings.database.port)
    # Output: 6543


anyio.run(main)
