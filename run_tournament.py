import json
import os
from pathlib import Path
import time
import csv


from utils.runners import run_tournament, process_tournament_results

RESULTS_DIR = Path("results", time.strftime('%Y%m%d-%H%M%S'))

# create results directory if it does not exist
if not RESULTS_DIR.exists():
    RESULTS_DIR.mkdir(parents=True)

# Settings to run a negotiation session:
#   You need to specify the classpath of 2 agents to start a negotiation. Parameters for the agent can be added as a dict (see example)
#   You need to specify the preference profiles for both agents. The first profile will be assigned to the first agent.
#   You need to specify a time deadline (is milliseconds (ms)) we are allowed to negotiate before we end without agreement.
tournament_settings = {
    "agents": [
        {
            "class": "agents.negotiating_agent.negotiating_agent.NegotiatingAgent",
            "parameters": {"storage_dir": "agent_storage/NegotiatingAgent"},
        },
        {
            "class": "agents.ANL2022.dreamteam109_agent.dreamteam109_agent.DreamTeam109Agent",
            "parameters": {"storage_dir": "agent_storage/DreamTeam109Agent"},
        },
        {
            "class": "agents.boulware_agent.boulware_agent.BoulwareAgent",
        },
        {
            "class": "agents.conceder_agent.conceder_agent.ConcederAgent",
        },
        {
            "class": "agents.hardliner_agent.hardliner_agent.HardlinerAgent",
        },
        {
            "class": "agents.linear_agent.linear_agent.LinearAgent",
        },
        {
            "class": "agents.random_agent.random_agent.RandomAgent",
        },
        {
            "class": "agents.stupid_agent.stupid_agent.StupidAgent",
        },
        # {
        #     "class": "agents.CSE3210.agent2.agent2.Agent2",
        # },
        # {
        #     "class": "agents.CSE3210.agent3.agent3.Agent3",
        # },
        # {
        #     "class": "agents.CSE3210.agent7.agent7.Agent7",
        # },
        # {
        #     "class": "agents.CSE3210.agent11.agent11.Agent11",
        # },
        # {
        #     "class": "agents.CSE3210.agent14.agent14.Agent14",
        # },
        # {
        #     "class": "agents.CSE3210.agent18.agent18.Agent18",
        # },
        # {
        #     "class": "agents.CSE3210.agent19.agent19.Agent19",
        # },
        # {
        #     "class": "agents.CSE3210.agent22.agent22.Agent22",
        # },
        # {
        #     "class": "agents.CSE3210.agent24.agent24.Agent24",
        # },
        # {
        #     "class": "agents.CSE3210.agent25.agent25.Agent25",
        # },
        # {
        #     "class": "agents.CSE3210.agent26.agent26.Agent26",
        # },
        # {
        #     "class": "agents.CSE3210.agent27.agent27.Agent27",
        # },
        # {
        #     "class": "agents.CSE3210.agent29.agent29.Agent29",
        # },
        # {
        #     "class": "agents.CSE3210.agent32.agent32.Agent32",
        # },
        # {
        #     "class": "agents.CSE3210.agent33.agent33.Agent33",
        # },
        # {
        #     "class": "agents.CSE3210.agent41.agent41.Agent41",
        # },
        # {
        #     "class": "agents.CSE3210.agent43.agent43.Agent43",
        # },
        # {
        #     "class": "agents.CSE3210.agent50.agent50.Agent50",
        # },
        # {
        #     "class": "agents.CSE3210.agent52.agent52.Agent52",
        # },
        # {
        #     "class": "agents.CSE3210.agent55.agent55.Agent55",
        # },
        # {
        #     "class": "agents.CSE3210.agent58.agent58.Agent58",
        # },
        # {
        #     "class": "agents.CSE3210.agent61.agent61.Agent61",
        # },
        # {
        #     "class": "agents.CSE3210.agent64.agent64.Agent64",
        # },
        # {
        #     "class": "agents.CSE3210.agent67.agent67.Agent67",
        # },
        # {
        #     "class": "agents.CSE3210.agent68.agent68.Agent68",
        # },
    ],
    "profile_sets": [
        ["domains/domain00/profileA.json", "domains/domain00/profileB.json"],
        ["domains/domain01/profileA.json", "domains/domain01/profileB.json"],
    ],
    "deadline_time_ms": 1000,
}

# run a session and obtain results in dictionaries
tournament_steps, tournament_results, tournament_results_summary = run_tournament(tournament_settings)

# save the tournament settings for reference
with open(RESULTS_DIR.joinpath("tournament_steps.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps(tournament_steps, indent=2))
# save the tournament results
with open(RESULTS_DIR.joinpath("tournament_results.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps(tournament_results, indent=2))
# save the tournament results summary
tournament_results_summary.to_csv(RESULTS_DIR.joinpath("tournament_results_summary.csv"))

our_agent = []
for result in tournament_results:
    if "NegotiatingAgent" in result.values():
        nr_offers = None
        utility = None
        nash = None
        social = None
        res = None
        nr = None
        vs = None
        for (key, value) in result.items():
            if key == "num_offers":
                nr_offers = value
            elif key == "nash_product":
                nash = value
            elif key == "social_welfare":
                social = value
            elif key == "result":
                res = value
            elif "agent" in key and value == "NegotiatingAgent":
                nr = key.split("_")[1]
            elif nr is not None and ("utility_"+nr) == key:
                utility = value
            elif "agent" in key:
                vs = value

        agree = 0
        fail = 0
        error = 0
        if res == "agreement":
            agree = 1
        elif res == "failed":
            fail = 1
        else:
            error = 1


        curr_op = None
        for op in our_agent:
            if op["name"] == vs:
                curr_op = op
                break

        if curr_op is not None:
            curr_op["count"] = curr_op["count"] + 1
            curr_op["avg_num_offers"].append(nr_offers)
            curr_op["avg_utility"].append(utility)
            curr_op["avg_nash_product"].append(nash)
            curr_op["avg_social_welfare"].append(social)
            curr_op["agreement"] = curr_op["agreement"] + agree
            curr_op["failed"] = curr_op["failed"] + fail
            curr_op["ERROR"] = curr_op["ERROR"] + error

        else:
            curr = {
                "name" : vs,
                "count" : 1,
                "avg_num_offers": [nr_offers],
                "avg_utility": [utility],
                "avg_nash_product": [nash],
                "avg_social_welfare": [social],
                "agreement": agree,
                "failed": fail,
                "ERROR": error
            }
            our_agent.append(curr)

for stats in our_agent:
    count = stats["count"]
    stats["avg_num_offers"] = sum(stats["avg_num_offers"])/count
    stats["avg_utility"] = sum(stats["avg_utility"])/count
    stats["avg_nash_product"] = sum(stats["avg_nash_product"])/count
    stats["avg_social_welfare"] = sum(stats["avg_social_welfare"])/count

# save our agent results
with open(RESULTS_DIR.joinpath("our_agent_results.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps(our_agent, indent=2))

our_agent_csv = [[
        " ",
        "avg_utility",
        "avg_nash_product",
        "avg_social_welfare",
        "avg_num_offers",
        "count",
        "agreement",
        "failed",
        "ERROR",
    ]]
for stats in our_agent:
    our_agent_csv.append([
        stats["name"],
        stats["avg_utility"],
        stats["avg_nash_product"],
        stats["avg_social_welfare"],
        stats["avg_num_offers"],
        stats["count"],
        stats["agreement"],
        stats["failed"],
        stats["ERROR"]
    ])

with open(RESULTS_DIR.joinpath("our_agent.csv"), "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(our_agent_csv)