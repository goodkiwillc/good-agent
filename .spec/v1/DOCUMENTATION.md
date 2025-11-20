# Documentation TODO

"work in progress" status - make it clear on the home page that the library is still being actively developed and documented.


Reorganize "Agent Components":
- [ ] Change "Extensibility" to "Components"

First page details the AgentComponent class system:
 - Registration
    - Install method
    - Same component can be added to multiple agents
 - Type-safe access on Agent instance via agent[ComponentClass]
 - Component access via dependency injection in tools, event handlers, context providers
 - Component can have tool methods


Need a full section for Templating
 - context
    - stack
    - providers
 - custom section filters



Tools

- the current page "Custom Tools" is under Extensibility - this should belong under Tools


Dependency Injection

- State that we use the FastDepends library for DI
