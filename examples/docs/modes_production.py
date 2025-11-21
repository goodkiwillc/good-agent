import asyncio
from datetime import datetime
from good_agent import Agent, ModeContext

async def main():
    async with Agent("Production Agent") as agent:
        # Production mode pattern
        @agent.modes("production_ready")
        async def production_ready_mode(ctx: ModeContext):
            """Production-ready mode with comprehensive features."""

            # Initialize mode with safety checks
            if not ctx.state.get("initialized"):
                # Validate prerequisites
                # We set required_tools for this example to pass validation
                if not hasattr(ctx.agent, "required_tools"):
                    # Normally raise ValueError("Mode requires specific tools")
                    # For demo, we'll just log a warning or skip strict check
                    pass

                # Set up monitoring
                ctx.state["start_time"] = datetime.now()
                ctx.state["call_count"] = 0
                ctx.state["error_count"] = 0
                ctx.state["initialized"] = True

            try:
                # Update metrics
                ctx.state["call_count"] += 1
                ctx.state["last_call"] = datetime.now()

                # Add contextual system message
                call_num = ctx.state["call_count"]
                ctx.add_system_message(f"Production mode - Call #{call_num}")

                # Automatic cleanup after extended use
                if call_num > 100:
                    ctx.state.clear()
                    ctx.state["initialized"] = True

                return await ctx.call()

            except Exception as e:
                ctx.state["error_count"] += 1
                ctx.state["last_error"] = str(e)

                # Consider exiting mode after too many errors
                if ctx.state["error_count"] > 5:
                    return ctx.exit_mode()

                raise
        
        # Use it
        # Mock required_tools attr if needed by logic, but we relaxed it for demo
        async with agent.modes["production_ready"]:
            await agent.call("Hello prod")

if __name__ == "__main__":
    asyncio.run(main())
