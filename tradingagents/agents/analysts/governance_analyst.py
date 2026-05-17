from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_company_announcements,
    get_insider_transactions,
    get_institutional_holdings,
    get_language_instruction,
    get_news,
    get_northbound_hold,
    get_restricted_release,
)
from tradingagents.dataflows.config import get_config


def create_governance_analyst(llm):
    def governance_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(
            state["company_of_interest"], state.get("company_name", "")
        )

        tools = [
            get_company_announcements,
            get_insider_transactions,
            get_news,
            get_restricted_release,
            get_institutional_holdings,
            get_northbound_hold,
        ]

        system_message = (
            "You are a Corporate Governance Analyst tasked with analyzing "
            "company announcements, shareholder changes, insider transactions, "
            "and major corporate events for a specific company over the past week. "
            "Your objective is to write a comprehensive long report detailing your "
            "analysis, insights, and implications for traders and investors. "
            "Use the get_company_announcements tool for regulatory filings and notices, "
            "get_insider_transactions for shareholder change data, get_news "
            "for related news coverage, get_restricted_release to identify upcoming "
            "share unlock events and their potential supply pressure, "
            "get_institutional_holdings to track top shareholder and fund positioning, "
            "and get_northbound_hold to monitor foreign investor sentiment. "
            "Provide specific, actionable insights on governance risks, capital structure "
            "changes, management signals, and any red flags that could impact investment decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "governance_report": report,
        }

    return governance_analyst_node
