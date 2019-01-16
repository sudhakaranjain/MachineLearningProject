import gym
import numpy as np
from keras.models import Sequential
from keras.layers import Dense
from keras.optimizers import SGD
import progressbar
import logging
from bipedalwalker.utils import utils
import math


EPISODES = 10000
MAX_TIMESTEPS = 1600  # It is 2000 for hardcore..


class spgModel:
    def __init__(self, state_size, action_size, action_min, action_max):
        self.state_size = state_size
        self.action_size = action_size
        self.replay_buffer = utils.Memory(4000)
        self.action_space_low = action_min
        self.action_space_high = action_max
        self.stateRMS = utils.obsRunningMeanStd(state_size)
        # HyperParams
        self.gamma = 0.99  # Discount rate
        # self.critic_lr = 1e-3
        # self.actor_lr = 1e-4
        self.critic_lr = 0.01
        self.actor_lr = 0.01
        self.critic_lr_decay = 1e-06
        self.actor_lr_decay = 1e-06
        self.sigma = 1.0
        self.sigma_min = 0.1
        self.sigma_decay = 0.9995
        self.batch_size = 32
        self.n_iter = 10
        # self.n_iter = 100
        self.n_sampled_actions = 3
        # Build NN
        self.critic_model = self._build_critic_model()
        self.actor_model = self._build_actor_model()

    def get_hyper_params(self):
        params = (self.gamma,
                  self.critic_lr,
                  self.actor_lr,
                  self.critic_lr_decay,
                  self.actor_lr_decay,
                  self.sigma,
                  self.sigma_min,
                  self.sigma_decay,
                  self.batch_size,
                  self.n_iter,
                  self.n_sampled_actions)
        return params

    def _build_critic_model(self):
        model = Sequential()
        model.add(Dense(100, input_dim=(self.state_size+self.action_size), activation='sigmoid'))
        # model.add(Dense(100, activation='relu'))
        model.add(Dense(1, activation='linear'))
        sgd = SGD(lr=self.critic_lr, momentum=0.8, decay=self.critic_lr_decay)
        model.compile(loss='mean_squared_error', optimizer=sgd)
        return model

    def _build_actor_model(self):
        model = Sequential()
        model.add(Dense(100, input_dim=self.state_size, activation='sigmoid'))
        # model.add(Dense(100, activation='relu'))
        model.add(Dense(self.action_size, activation='tanh'))
        sgd = SGD(lr=self.actor_lr, momentum=0.8, decay=self.actor_lr_decay)
        model.compile(loss='mean_squared_error', optimizer=sgd)
        return model

    def exploration(self, state, action_space):  # SPG-OffGE - offline Gaussian exploration
        act_values = self.actor_model.predict(state)
        actions = act_values + np.random.normal(0, self.sigma, size=action_space)
        actions = actions.clip(self.action_space_low, self.action_space_high)
        return actions[0]

    def train_critic(self):
        for _ in range(self.n_iter):
            state, action, reward, next_state, done = self.replay_buffer.sample(self.batch_size)
            for i in range(self.batch_size):
                # st, rt, st1 = np.reshape(state[i], (1, self.state_size)), reward[i], np.reshape(next_state[i], (1, self.state_size))
                st = np.reshape(utils.normalize(state[i], self.stateRMS), (1, self.state_size))
                st1 = np.reshape(utils.normalize(next_state[i], self.stateRMS), (1, self.state_size))
                rt = reward[i]
                pi_st = self.actor_model.predict(st)
                pi_st1 = self.actor_model.predict(st1)
                st_pit = np.hstack((st, pi_st))
                if done[i]:
                    target_critic = np.reshape(rt, (1, 1))
                else:
                    target_critic = rt + self.gamma*self.get_Q(st1, pi_st1)
                print("target: {}".format(target_critic))  # TODO:delete, just for debug
                self.critic_model.fit(st_pit, target_critic, epochs=1, verbose=0)

    def train_actor(self):
        dafuk = False
        for _ in range(self.n_iter):
            state, action, reward, next_state, done = self.replay_buffer.sample(self.batch_size)
            for i in range(self.batch_size):
                # s, a = np.reshape(state[i], (1, self.state_size)), np.reshape(action[i], (1, self.action_size))
                s = np.reshape(utils.normalize(state[i], self.stateRMS), (1, self.state_size))
                a = np.reshape(action[i], (1, self.action_size))
                pi_s = self.actor_model.predict(s)
                best = pi_s
                if math.isnan(self.get_Q(s, a)):  # TODO: delete this...
                    dafuk = True
                if self.get_Q(s, a) > self.get_Q(s, pi_s):
                    best = a
                for _ in range(self.n_sampled_actions):
                    sampled = self.apply_gaussian(best)
                    if self.get_Q(s, sampled) > self.get_Q(s, best):
                        best = sampled
                if self.get_Q(s, best) > self.get_Q(s, pi_s):
                    target = best
                    self.actor_model.fit(s, target, epochs=1, verbose=0)
        if dafuk == True:
            print("dafuk is happening")

    def apply_gaussian(self, best_action):
        best_action = best_action + np.random.normal(0, self.sigma, size=self.action_size)
        return best_action.clip(self.action_space_low, self.action_space_high)

    def get_Q(self, state, actions):
        return self.critic_model.predict(np.hstack((state, actions)))

    def save(self, critic_filename, actor_filename):
        self.critic_model.save_weights(critic_filename)
        self.actor_model.save_weights(actor_filename)

    def load(self, critic_filename, actor_filename):
        self.critic_model.load_weights(critic_filename)
        self.actor_model.load_weights(actor_filename)


if __name__ == "__main__":

    # logging.basicConfig(filename='output.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.basicConfig(filename='output.log', level=logging.DEBUG, format='%(message)s')
    env = gym.make('BipedalWalker-v2')
    state_size = env.observation_space.shape[0]
    action_size = env.action_space.shape[0]
    model = spgModel(state_size, action_size, env.action_space.low, env.action_space.high)
    critic_filename = "BipedalWalker-critic.h5"
    actor_filename = "BipedalWalker-actor.h5"

    logging.info("Starting exercise: actor_filename: {}, critic_filename: {}\n".format(actor_filename, critic_filename))
    paramList = ["gamma",
                 "critic_lr",
                 "actor_lr",
                 "critic_lr_decay",
                 "actor_lr_decay",
                 "sigma",
                 "sigma_min",
                 "sigma_decay",
                 "batch_size",
                 "n_iter",
                 "n_SampledActions"]

    msg = utils.print_hyperparam(paramList, model.get_hyper_params())
    logging.info(msg)

    # model.load(critic_filename, actor_filename)
    # model.sigma = 0.0

    avg_reward = 0
    ep_reward = 0

    # Train the RMS a bit before start normalizing
    for i in range(20):
        state = env.reset()
        done = False
        while not done:
            model.stateRMS.update(state, state_size)
            next_state, reward, done, _ = env.step(env.action_space.sample())
            state = next_state
            # if done:
            #     model.stateRMS.print()

    # Main loop for episodes.
    for e in progressbar.progressbar(range(EPISODES)):
        state = env.reset()
        finishLine = False

        for t in range(MAX_TIMESTEPS):
            # env.render()

            # Updating running mean and deviation for the state vector.
            model.stateRMS.update(state, state_size)

            # Performing an action.
            norm_state = utils.normalize(state, model.stateRMS)
            actions = model.exploration(np.reshape(norm_state, (1, state_size)), action_size)
            next_state, reward, done, _ = env.step(actions)

            # Measurements of progress.
            posX = env.env.hull.position.x
            x_vel = state[2]
            finishLine = ((reward > 200.0) or (posX > 20))
            if finishLine:
                logging.warning("Hallelujah! reward: {}, posX: {}".format(reward, posX))

            # Save values to buffer
            model.replay_buffer.remember(state, actions, reward, next_state, done)
            state = next_state

            avg_reward += reward
            ep_reward += reward

            if done:
                # Train model.
                model.train_critic()
                model.train_actor()

                # Output variables to log.
                paramList = ["latest_r",
                             "ep_reward",
                             "avg_reward",
                             "sigma",
                             "posX",
                             "t"]
                params = (e+1, EPISODES, reward, ep_reward, avg_reward, model.sigma, posX, t)
                msg = utils.print_episode(paramList, params)
                logging.debug(msg)

                # Sigma decay.
                if model.sigma > model.sigma_min:
                    model.sigma *= model.sigma_decay
                else:
                    model.sigma = model.sigma_min

                break

        ep_reward = 0
        model.save(critic_filename, actor_filename)