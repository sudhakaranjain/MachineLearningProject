import random
import gym
import numpy as np
from scipy import integrate
from collections import deque
from keras.models import Sequential
from keras.layers import Dense
from keras.optimizers import Adam
import sys
import progressbar
import logging


EPISODES = 10000
FPS = 50
dt = 1/FPS


class CACLACritic:
    def __init__(self, state_size, action_size):
        self.state_size = state_size
        self.action_size = action_size
        self.gamma = 0.99  # Discount rate
        self.learning_rate = 0.01
        self.model = self._build_model()

    def _build_model(self):  # Neural Net for CACLA learning Model - critic
        model = Sequential()
        model.add(Dense(400, input_dim=self.state_size, activation='relu'))
        model.add(Dense(300, activation='relu'))
        model.add(Dense(1, activation='linear'))  # Returns the Value for best policy
        model.compile(loss='mse', optimizer=Adam(lr=self.learning_rate))
        return model

    def learn(self, state, reward, next_state):
        target = reward + self.gamma*self.model.predict(next_state)
        self.model.fit(state, target, epochs=1, verbose=0)

    def getTDE(self, state, reward, next_state):
        target = reward + self.gamma*self.model.predict(next_state)
        return target - self.model.predict(state)

    def load(self, name):
        self.model.load_weights(name)

    def save(self, name):
        self.model.save_weights(name)


class CACLAActor:
    def __init__(self, state_size, action_size):
        self.state_size = state_size
        self.action_size = action_size
        self.sigma = 0.7
        self.sigma_min = 0.2
        self.sigma_decay = 0.999
        self.learning_rate = 0.01
        self.model = self._build_model()

    def _build_model(self):  # Neural Net for CACLA learning Model - actor
        model = Sequential()
        model.add(Dense(400, input_dim=self.state_size, activation='relu'))
        model.add(Dense(300, activation='relu'))
        model.add(Dense(self.action_size, activation='tanh'))
        model.compile(loss='mse',
                      optimizer=Adam(lr=self.learning_rate))
        return model

    def act(self, state):
        act_values = self.model.predict(state)[0]
        actions = []  # Actions to perform using a Gaussian exploration method
        actions = act_values + np.random.normal(0, self.sigma, size=env.action_space.shape[0])
        actions = actions.clip(env.action_space.low, env.action_space.high)
        #for val in act_values[0]:
            #actions.append(np.random.normal(0, self.sigma, size=env.action_space.shape[0]))
            #actions.append(np.random.normal(val, self.sigma))
        return np.array(actions)

    def learn(self, state, action, tempDiffErr):
        if tempDiffErr > 0:
            target = action
            self.model.fit(state, target, epochs=1, verbose=0)
            # if self.sigma > self.sigma_min:
            #     self.sigma *= self.sigma_decay

    def load(self, name):
        self.model.load_weights(name)

    def save(self, name):
        self.model.save_weights(name)


if __name__ == "__main__":

    logging.basicConfig(filename='output.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    env = gym.make('BipedalWalker-v2')
    state_size = env.observation_space.shape[0]
    action_size = env.action_space.shape[0]
    actor = CACLAActor(state_size, action_size)
    critic = CACLACritic(state_size, action_size)

    actor_filename = "BipedalWalker-actor.h5"
    critic_filename = "BipedalWalker-critic.h5"

    X_vel_offset = 30.0

    # so we can train it with different params
    if len(sys.argv) > 1:
        actor.sigma_decay = float(sys.argv[1])
        X_vel_offset = float(sys.argv[2])
        actor_filename = sys.argv[3]
        critic_filename = sys.argv[4]
    logging.info("Starting exercise: actor_filename: {}, critic_filename: {}, sigmadecay: {}, xvel: {}".format(actor_filename, critic_filename, actor.sigma_decay, X_vel_offset))

    #actor.load(actor_filename)
    #critic.load(critic_filename)
            
    batch = []
    for e in progressbar.progressbar(range(EPISODES)):
        state = env.reset()
        state = np.reshape(state, [1, state_size])
        # Initialize the X position after reset. We will use this to calculate reward
        posX = 0.0
        velX_array = []
        done = False
 
        totalReward = 0
        while not done:
            #env.render()
            if e > 500:
    	        env.render()
            action = actor.act(state)
            next_state, reward, done, _ = env.step(action)

            velX_array.append(state[0][2])
            posX = env.env.hull.position.x
            
            #TODO: extra reward stuff, prob not needed
            #posX = integrate.trapz(velX_array, dx=dt)
            #posXRewardFactor = 100.0
            #reward += posXRewardFactor*posX
            #if(posX>0.3 and x_vel > 0):
            #   reward += x_vel

            #if(done and posX<0.3):
            #   reward += -30

            # TODO: WHAT IF WE INTEGRATE THE VEL TO GET POS AND THEN REWARD BASED ON HOW FAR WE MOVED
            x_vel = state[0][2]
            # r_X_vel = X_vel_offset
            # if x_vel > 0:
            #     reward += r_X_vel*x_vel

            next_state = np.reshape(next_state, [1, state_size])
            action = np.reshape(action, [1, action_size])
            # logging.debug("actions: {}".format(action))
            tempDiffErr = critic.getTDE(state, reward, next_state)
            
            state = next_state
            batch.append([state, action, reward, tempDiffErr, next_state])
            totalReward += reward

            if done:
                for iteration in batch:
                    stateB = iteration[0]
                    actionB = iteration[1]
                    rewardB = iteration[2]
                    tempDiffErrB = iteration[3]
                    next_stateB = iteration[4]
                    actor.learn(stateB, actionB, tempDiffErrB)
                    critic.learn(stateB, rewardB, next_stateB)
                    
                batch = []
                actor.save(actor_filename)
                critic.save(critic_filename)
                
                logging.debug("episode: {}/{}, sigma: {:.2}, posX: {}, velX: {}, totalreward: {}"
                              .format(e, EPISODES, actor.sigma, posX, x_vel, totalReward))
                if reward > 100:
                    logging.warning("Hallelujah! reward: {}".format(reward))
                if actor.sigma > actor.sigma_min:
                    actor.sigma *= actor.sigma_decay

  
