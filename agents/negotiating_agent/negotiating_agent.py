import logging
import numpy as np
import numpy.ma as mask
from random import randint
from time import time
from typing import cast

from geniusweb.actions.Accept import Accept
from geniusweb.actions.Action import Action
from geniusweb.actions.Offer import Offer
from geniusweb.actions.PartyId import PartyId
from geniusweb.bidspace.AllBidsList import AllBidsList
from geniusweb.inform.ActionDone import ActionDone
from geniusweb.inform.Finished import Finished
from geniusweb.inform.Inform import Inform
from geniusweb.inform.Settings import Settings
from geniusweb.inform.YourTurn import YourTurn
from geniusweb.issuevalue.Bid import Bid
from geniusweb.issuevalue.Domain import Domain
from geniusweb.party.Capabilities import Capabilities
from geniusweb.party.DefaultParty import DefaultParty
from geniusweb.profile.utilityspace.LinearAdditiveUtilitySpace import (
    LinearAdditiveUtilitySpace,
)
from geniusweb.profileconnection.ProfileConnectionFactory import (
    ProfileConnectionFactory,
)
from geniusweb.progress.ProgressTime import ProgressTime
from geniusweb.references.Parameters import Parameters
from tudelft_utilities_logging.ReportToLogger import ReportToLogger

from .utils.opponent_model import OpponentModel


class NegotiatingAgent(DefaultParty):

    def __init__(self):
        super().__init__()
        self.logger: ReportToLogger = self.getReporter()

        self.domain: Domain = None
        self.parameters: Parameters = None
        self.profile: LinearAdditiveUtilitySpace = None
        self.progress: ProgressTime = None
        self.me: PartyId = None
        self.other: str = None
        self.settings: Settings = None
        self.storage_dir: str = None

        self.last_proposed_bid: Bid = None
        self.last_received_bid: Bid = None
        self.opponent_model: OpponentModel = None
        self.logger.log(logging.INFO, "party is initialized")

        self.lowest_bid: float = 1.0
        self.reservation_value: float = 0.6
        self.bids = None
        self.scores = None
        self.opponent_scores = None
        self.arg_sort = None
        self.count = 0

    def notifyChange(self, data: Inform):
        """MUST BE IMPLEMENTED
        This is the entry point of all interaction with your agent after is has been initialised.
        How to handle the received data is based on its class type.

        Args:
            info (Inform): Contains either a request for action or information.
        """

        # a Settings message is the first message that will be send to your
        # agent containing all the information about the negotiation session.
        if isinstance(data, Settings):
            self.settings = cast(Settings, data)
            self.me = self.settings.getID()

            # progress towards the deadline has to be tracked manually through the use of the Progress object
            self.progress = self.settings.getProgress()

            self.parameters = self.settings.getParameters()
            self.storage_dir = self.parameters.get("storage_dir")

            # the profile contains the preferences of the agent over the domain
            profile_connection = ProfileConnectionFactory.create(
                data.getProfile().getURI(), self.getReporter()
            )
            self.profile = profile_connection.getProfile()
            self.domain = self.profile.getDomain()
            profile_connection.close()

        # ActionDone informs you of an action (an offer or an accept)
        # that is performed by one of the agents (including yourself).
        elif isinstance(data, ActionDone):
            action = cast(ActionDone, data).getAction()
            actor = action.getActor()

            # ignore action if it is our action
            if actor != self.me:
                # obtain the name of the opponent, cutting of the position ID.
                self.other = str(actor).rsplit("_", 1)[0]

                # process action done by opponent
                self.opponent_action(action)
        # YourTurn notifies you that it is your turn to act
        elif isinstance(data, YourTurn):
            # execute a turn
            self.my_turn()

        # Finished will be send if the negotiation has ended (through agreement or deadline)
        elif isinstance(data, Finished):
            self.save_data()
            # terminate the agent MUST BE CALLED
            self.logger.log(logging.INFO, "party is terminating:")
            super().terminate()
        else:
            self.logger.log(logging.WARNING, "Ignoring unknown info " + str(data))

    def getCapabilities(self) -> Capabilities:
        """MUST BE IMPLEMENTED
        Method to indicate to the protocol what the capabilities of this agent are.
        Leave it as is for the ANL 2022 competition

        Returns:
            Capabilities: Capabilities representation class
        """
        return Capabilities(
            set(["SAOP"]),
            set(["geniusweb.profile.utilityspace.LinearAdditive"]),
        )

    def send_action(self, action: Action):
        """Sends an action to the opponent(s)

        Args:
            action (Action): action of this agent
        """
        self.getConnection().send(action)

    # give a description of your agent
    def getDescription(self) -> str:
        """MUST BE IMPLEMENTED
        Returns a description of your agent. 1 or 2 sentences.

        Returns:
            str: Agent description
        """
        return "Negotiating agent by Group 25"

    def opponent_action(self, action):
        """Process an action that was received from the opponent.

        Args:
            action (Action): action of opponent
        """
        # if it is an offer, set the last received bid
        if isinstance(action, Offer):
            # create opponent model if it was not yet initialised
            if self.opponent_model is None:
                self.opponent_model = OpponentModel(self.domain)

            bid = cast(Offer, action).getBid()

            # update opponent model with bid
            self.opponent_model.update(bid)
            # set bid as last received
            self.last_received_bid = bid

    def my_turn(self):
        """This method is called when it is our turn. It should decide upon an action
        to perform and send this action to the opponent.
        """
        bid = self.find_bid()
        # check if the last received offer is good enough
        if self.accept_condition(self.last_received_bid, bid):
            # if so, accept the offer
            action = Accept(self.me, self.last_received_bid)
        else:
            # if not, find a bid to propose as counter offer
            action = Offer(self.me, bid)
        # send the action
        self.last_proposed_bid = bid
        self.send_action(action)

    def save_data(self):
        """This method is called after the negotiation is finished. It can be used to store data
        for learning capabilities. Note that no extensive calculations can be done within this method.
        Taking too much time might result in your agent being killed, so use it for storage only.
        """
        data = "Data for learning (see README.md)"
        with open(f"{self.storage_dir}/data.md", "w") as f:
            f.write(data)

    ###########################################################################################
    ################################## Example methods below ##################################
    ###########################################################################################

    def accept_condition(self, bid: Bid, next_bid: Bid) -> bool:
        if bid is None:
            return False

        # progress of the negotiation session between 0 and 1 (1 is deadline)
        progress = self.progress.get(time() * 1000)

        # check if the offer is valued above the max value between alpha and the reservation value
        alpha = 0.8
        if self.profile.getUtility(bid) >= min(self.lowest_bid + 0.05, alpha):
            ac_const = True
        else:
            ac_const = False

        # check if the bid is better than upcoming bid
        if next_bid is not None:
            ac_next = self.profile.getUtility(bid) >= self.profile.getUtility(next_bid)
        else:
            ac_next = False

        # check if 98% of the time has passed
        if progress > 0.98:
            ac_time = True
        else:
            ac_time = False

        # ac_combi = true if ac_next or ac_time are true and if ac_const is true
        ac_combi = (ac_next or ac_time) and ac_const
        return ac_combi

    def random_bid_generator(self, n: int):
        domain = self.profile.getDomain()
        all_bids = AllBidsList(domain)
        to_go = list(range(all_bids.size()))
        for _ in range(n):
            if len(to_go) == 0:
                break
            index = randint(0, len(to_go)-1)
            yield all_bids.get(to_go.pop(index))

    def find_bid(self) -> Bid:

        progress = self.progress.get(time() * 1000)  # 0.9

        if self.bids is None:
            # attempt to draw 10_000 bids, discard the useless ones.
            # then preconfigure it for later stages and calculate all the scores
            # only retain the best set of bids in self.arg_sort to offer during the initial bidding stage
            generator = self.random_bid_generator(10000)
            bid_val = [(bid, float(self.profile.getUtility(bid))) for bid in generator if self.profile.getUtility(bid) > self.reservation_value]
            self.bids = np.array([x[0] for x in bid_val])
            self.scores = np.array([x[1] for x in bid_val])
            self.arg_sort = np.where(self.scores > 0.9)
            if len(self.arg_sort) < 10:
                self.arg_sort = np.flip(np.argsort(self.scores))[:50]

        # first halve we just model the opponent, so we only propose valid bids for us
        if progress < 0.85:
            return self.bids[np.random.choice(self.arg_sort)]
        else:
            self.count += 1
            # refresh scores every so often as opponent might also start conceding from here.
            if self.opponent_scores is None or self.count % 20 == 0:
                self.opponent_scores = np.array([self.opponent_model.get_predicted_utility(bid) for bid in self.bids])

            # Get the indices of the bids we care about
            # with those indices index into opponent_scores
            # get the argmax, this argmax bids[bids_we_care_about[argmax_of_opponent_scores]]

            # centre of the domain that we will pick from
            upper_thresh = 0.99 if self.last_proposed_bid is None else float(self.profile.getUtility(self.last_proposed_bid))
            delta = 0.05  # concession delta
            indices_we_care_about = np.where((upper_thresh+delta > self.scores) & (self.scores > upper_thresh-delta))[0]
            if len(indices_we_care_about) == 0:
                # this is a failsafe on the off chance that upper_thresh is too high with no known last bid.
                return self.bids[np.random.choice(self.arg_sort)]
            possible_utilities_for_the_opponent = self.opponent_scores[indices_we_care_about]
            final_index = indices_we_care_about[np.random.choice(np.flip(np.argsort(possible_utilities_for_the_opponent))[:5])]
            self.lowest_bid = min(self.lowest_bid, self.scores[final_index])
            return self.bids[final_index]

