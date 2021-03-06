# 
# Implementation of the BEE simulator example using SpiNNaker.
# 

# The neuron model used with BEE is this:
lsm_neuron_eqs='''
  dv/dt  = (ie + ii + i_offset + i_noise)/c_m + (v_rest-v)/tau_m : mV
  die/dt = -ie/tau_syn_E                : nA
  dii/dt = -ii/tau_syn_I                : nA
  tau_syn_E                             : ms
  tau_syn_I                             : ms
  tau_m                                 : ms
  c_m                                   : nF
  v_rest                                : mV
  i_offset                              : nA
  i_noise                               : nA
  '''
# Using SpiNNaker it's not possible to inject gaussian noise into i_noise during the simulation.
# One solution is to use an external Poisson spike source (SpikeSourcePoisson) to emulate the noisy current.
# But i_noise should have mean value zero, so it's necessary two Poisson sources (one positive and other negative).

# Don't forget to properly setup:
# /home/simulators/.spynnaker.cfg and /usr/local/lib/python2.7/dist-packages/spynnaker/spynnaker.cfg

import spynnaker.pyNN as sim
import spynnaker_external_devices_plugin.pyNN as ExternalDevices
import spinnman.messages.eieio.eieio_type as eieio_type

import numpy

import pylab

# host_IP = '192.169.110.2' # when Spinn-3 is connected
# host_IP = '192.168.1.2' # when Spinn-5 is connected

# Base code from:
# http://spinnakermanchester.github.io/2015.005.Arbitrary/workshop_material/

simulation_timestep = 0.2

sim.setup(timestep=simulation_timestep, min_delay=simulation_timestep, max_delay=simulation_timestep*144)


# Generate the connections matrix inside the Liquid (Liquid->Liquid) - according to Maass2002
#
print "Liquid->Liquid connections..."


Number_of_neurons_lsm=numpy.load("Number_of_neurons_lsm.npy")

#
# These are the cell (neuron) parameters according to Maass 2002
#
cell_params_lsm = {'cm'          : 30,    # Capacitance of the membrane 
                                             # =>>>> MAASS PAPER DOESN'T MENTION THIS PARAMETER DIRECTLY
                                             #       but the paper mentions a INPUT RESISTANCE OF 1MEGA Ohms and tau_m=RC=30ms, so cm=30nF
                   'i_offset'    : 0.0,   # Offset current - random for each neuron from [14.975nA to 15.025nA] => Masss2002 - see code below
                   'tau_m'       : 30.0,  # Membrane time constant => Maass2002
                   'tau_refrac_E': 3.0,   # Duration of refractory period - 3mS for EXCITATORY => Maass2002
                   'tau_refrac_I': 2.0,   # Duration of refractory period - 2mS for INHIBITORY => Maass2002
                   'tau_syn_E'   : 3.0,   # Decay time of excitatory synaptic current => Maass2002
                   'tau_syn_I'   : 6.0,   # Decay time of inhibitory synaptic current => Maass2002
                   'v_reset'     : 13.5,  # Reset potential after a spike => Maass2002
                   'v_rest'      : 0.0,   # Resting membrane potential => Maass2002
                   'v_thresh'    : 15.0,  # Spike threshold => Maass2002
                   'i_noise'     : 0.2    # Used in Maass2002: mean 0 and SD=0.2nA
                }


# Parameter of the neuron model LIF with exponential currents
cell_params_lif_exc = {
                        'tau_m': cell_params_lsm['tau_m'], 
                        'cm': cell_params_lsm['cm'], 
                         'v_rest': cell_params_lsm['v_rest'], 
                         'v_reset': cell_params_lsm['v_reset'],
                         'v_thresh': cell_params_lsm['v_thresh'], 
                         'tau_syn_E': cell_params_lsm['tau_syn_E'], 
                         'tau_syn_I': cell_params_lsm['tau_syn_I'],
                         'tau_refrac': cell_params_lsm['tau_refrac_E'],
                         'i_offset': cell_params_lsm['i_offset'], 
                         'v_init': 0.0
                      }
# The only difference is the refractory period
cell_params_lif_inh = {
                        'tau_m': cell_params_lsm['tau_m'], 
                        'cm': cell_params_lsm['cm'], 
                         'v_rest': cell_params_lsm['v_rest'], 
                         'v_reset': cell_params_lsm['v_reset'],
                         'v_thresh': cell_params_lsm['v_thresh'], 
                         'tau_syn_E': cell_params_lsm['tau_syn_E'], 
                         'tau_syn_I': cell_params_lsm['tau_syn_I'],
                         'tau_refrac': cell_params_lsm['tau_refrac_I'],
                         'i_offset': cell_params_lsm['i_offset'],
                         'v_init': 0.0
                      }                      

# The populations (exc and inh) are ordered as the arrays (exc_neuron_idx and inh_neuron_idx)below:
exc_neuron_idx = numpy.load("exc_neuron_idx.npy")
translate_exc_idx = dict(zip(exc_neuron_idx,range(len(exc_neuron_idx)))) 
# translate_exc_idx[BEE_index]=>spinnaker_index
# exc_neuron_idx[spinnaker_index]=>BEE_index

inh_neuron_idx = numpy.load("inh_neuron_idx.npy")
translate_inh_idx = dict(zip(inh_neuron_idx,range(len(inh_neuron_idx))))
# translate_inh_idx[BEE_index]=>spinnaker_index
# inh_neuron_idx[spinnaker_index]=>BEE_index

print "Liquid->Liquid connections... Populations"

# Creates two separated populations: one for excitatory neurons and other for inhibitory
# It's necessary to divide excitatory and inhibitory neurons because it's not possible to set
# different values for the refractory period inside the same population (using this old SpiNNaker version)
pop_lsm_exc = sim.Population(len(exc_neuron_idx), sim.IF_curr_exp, cell_params_lif_exc, label='LSM_EXC')
pop_lsm_inh = sim.Population(len(inh_neuron_idx), sim.IF_curr_exp, cell_params_lif_inh, label='LSM_INH')


# Brian and BEE use seconds instead of ms
# refractory_vector = ((numpy.load("refractory_vector.npy")*1E3).astype(numpy.int)).astype(numpy.double)
# pop_lsm.tset('tau_refrac',refractory_vector) # DOES NOT WORK!!!

# Parameters available using Spinnaker-PyNN:
# v_rest=default_parameters['v_rest'],
# v_reset=default_parameters['v_reset'],
# v_thresh=default_parameters['v_thresh'],
# tau_syn_E=default_parameters['tau_syn_E'],
# tau_syn_I=default_parameters['tau_syn_I'],
# tau_refrac=default_parameters['tau_refrac'],
# i_offset=default_parameters['i_offset'],
# v_init=default_parameters['v_init']):

i_offset = numpy.load("i_offset.npy")*1E9 # SpiNNaker uses nA
i_offset_exc = i_offset[exc_neuron_idx]
i_offset_inh = i_offset[inh_neuron_idx]
pop_lsm_exc.tset('i_offset',i_offset_exc)
pop_lsm_inh.tset('i_offset',i_offset_inh)


init_membrane_v = numpy.load("init_membrane_v.npy")*1E3 # SpiNNaker uses mV
init_membrane_v_exc = init_membrane_v[exc_neuron_idx]
init_membrane_v_inh = init_membrane_v[inh_neuron_idx]
pop_lsm_exc.tset('v_init',init_membrane_v_exc)
pop_lsm_inh.tset('v_init',init_membrane_v_inh)


#
# Creating the EXC to ??? connections
#
print "Liquid->Liquid connections... EXC to ???"

indices_pre_exc = numpy.load("indices_pre_exc.npy")
indices_pos_exc = numpy.load("indices_pos_exc.npy")
weights_pre_exc = numpy.load("weights_pre_exc.npy")

# First it's necessary to find which POS neurons are EXCITATORY and which ones are INHIBITORY:
temp_exc_pos = (numpy.array([indices_pos_exc == i for i in exc_neuron_idx])).sum(axis=0)
exc2exc = numpy.arange(len(indices_pos_exc))[temp_exc_pos==1] # excitatory ones
exc2inh = numpy.arange(len(indices_pos_exc))[temp_exc_pos==0] # inhibitory ones

# EXC2EXC
indices_pre_exc_e2e=[(numpy.abs(exc_neuron_idx-i)).argmin() for i in indices_pre_exc[exc2exc]]
indices_pos_exc_e2e=[(numpy.abs(exc_neuron_idx-i)).argmin() for i in indices_pos_exc[exc2exc]]

connections_exc2exc = sim.FromListConnector(conn_list=zip(indices_pre_exc_e2e,indices_pos_exc_e2e,weights_pre_exc[exc2exc],[0.0]*len(exc2exc)))
sim.Projection(pop_lsm_exc,pop_lsm_exc,connections_exc2exc,label="EXC2EXC_conn", target='excitatory')

# EXC2INH
indices_pre_exc_e2i=[(numpy.abs(inh_neuron_idx-i)).argmin() for i in indices_pre_exc[exc2inh]]
indices_pos_exc_e2i=[(numpy.abs(inh_neuron_idx-i)).argmin() for i in indices_pos_exc[exc2inh]]

connections_exc2inh = sim.FromListConnector(conn_list=zip(indices_pre_exc_e2i,indices_pos_exc_e2i,weights_pre_exc[exc2inh],[0.0]*len(exc2inh)))
sim.Projection(pop_lsm_exc,pop_lsm_inh,connections_exc2inh,label="EXC2INH_conn", target='excitatory')


#
# Creating the INH to ??? connections
#
print "Liquid->Liquid connections... INH to ???"
indices_pre_inh = numpy.load("indices_pre_inh.npy")
indices_pos_inh = numpy.load("indices_pos_inh.npy")
weights_pre_inh = numpy.load("weights_pre_inh.npy")

# First it's necessary to find which POS neurons are EXCITATORY and which ones are INHIBITORY:
temp_inh_pos = (numpy.array([indices_pos_inh == i for i in exc_neuron_idx])).sum(axis=0)
inh2exc = numpy.arange(len(indices_pos_inh))[temp_inh_pos==1] # excitatory ones
inh2inh = numpy.arange(len(indices_pos_inh))[temp_inh_pos==0] # inhibitory ones

# INH2EXC
indices_pre_inh_i2e=[(numpy.abs(exc_neuron_idx-i)).argmin() for i in indices_pre_inh[inh2exc]]
indices_pos_inh_i2e=[(numpy.abs(exc_neuron_idx-i)).argmin() for i in indices_pos_inh[inh2exc]]

connections_inh2exc = sim.FromListConnector(conn_list=zip(indices_pre_inh_i2e,indices_pos_inh_i2e,weights_pre_inh[inh2exc],[0.0]*len(inh2exc)))
sim.Projection(pop_lsm_inh,pop_lsm_exc,connections_inh2exc,label="INH2EXC_conn", target='inhibitory')

# INH2INH
indices_pre_inh_i2i=[(numpy.abs(inh_neuron_idx-i)).argmin() for i in indices_pre_inh[inh2inh]]
indices_pos_inh_i2i=[(numpy.abs(inh_neuron_idx-i)).argmin() for i in indices_pos_inh[inh2inh]]

connections_inh2inh = sim.FromListConnector(conn_list=zip(indices_pre_inh_i2i,indices_pos_inh_i2i,weights_pre_inh[inh2inh],[0.0]*len(inh2inh)))
sim.Projection(pop_lsm_inh,pop_lsm_inh,connections_inh2inh,label="INH2INH_conn", target='inhibitory')


poisson_rate = 500.0
pop_poisson_exc_p = sim.Population(len(exc_neuron_idx), sim.SpikeSourcePoisson, {"rate": poisson_rate})
pop_poisson_exc_n = sim.Population(len(exc_neuron_idx), sim.SpikeSourcePoisson, {"rate": poisson_rate})
pop_poisson_inh_p = sim.Population(len(inh_neuron_idx), sim.SpikeSourcePoisson, {"rate": poisson_rate})
pop_poisson_inh_n = sim.Population(len(inh_neuron_idx), sim.SpikeSourcePoisson, {"rate": poisson_rate})

poisson_weight = 0.005
sim.Projection(pop_poisson_exc_p, pop_lsm_exc, sim.OneToOneConnector(weights=poisson_weight))
sim.Projection(pop_poisson_exc_n, pop_lsm_exc, sim.OneToOneConnector(weights=-poisson_weight))
sim.Projection(pop_poisson_inh_p, pop_lsm_inh, sim.OneToOneConnector(weights=poisson_weight))
sim.Projection(pop_poisson_inh_n, pop_lsm_inh, sim.OneToOneConnector(weights=-poisson_weight))


#
# INPUT - Setup
#

print "Liquid->Liquid connections... Input Setup"

tspk = simulation_timestep*50 # The neurons spike after 50 time steps!
number_of_spikes = 500

spiketimes = [(i,tspk) for i in range(number_of_spikes)] 
                # The spikes are going to be received during the simulation, 
                # so this is always an empty list when using the step_by_step_brian_sim!

input_times = [tspk]

spikeArray = {'spike_times': [input_times for i in range(number_of_spikes)]}


input_spikes = sim.Population(number_of_spikes, sim.SpikeSourceArray, spikeArray, label='input_spikes')

input_weight = 100

input_connections_exc = [(i, translate_exc_idx[i], input_weight, 0) for i in range(number_of_spikes) if i in exc_neuron_idx]
sim.Projection(input_spikes, pop_lsm_exc, sim.FromListConnector(input_connections_exc))

input_connections_inh = [(i, translate_inh_idx[i], input_weight, 0) for i in range(number_of_spikes) if i in inh_neuron_idx]
sim.Projection(input_spikes, pop_lsm_inh, sim.FromListConnector(input_connections_inh))




pop_lsm_exc.record_v()
pop_lsm_exc.record()

pop_lsm_inh.record_v()
pop_lsm_inh.record()


sim.run(500*simulation_timestep)


v_exc = pop_lsm_exc.get_v(compatible_output=True)
v_inh = pop_lsm_inh.get_v(compatible_output=True)

spikes_exc = pop_lsm_exc.getSpikes(compatible_output=True)
spikes_inh = pop_lsm_inh.getSpikes(compatible_output=True)

pylab.figure()
pylab.plot([i[1] for i in spikes_exc], [exc_neuron_idx[int(i[0])] for i in spikes_exc], "r.")
pylab.plot([i[1] for i in spikes_inh], [inh_neuron_idx[int(i[0])] for i in spikes_inh], "b.")
pylab.xlabel('Time/ms')
pylab.ylabel('spikes')
pylab.title('spikes')
pylab.show()

# Make some graphs

# # All membrane voltages together
# ticks = len(v) / len(pop_lsm_exc)
# pylab.figure()
# pylab.xlabel('Time/ms')
# pylab.ylabel('v')
# pylab.title('v')
# for pos in range(0, len(pop_lsm_exc), 20):
#     v_for_neuron = v[pos * ticks: (pos + 1) * ticks]
#     pylab.plot([i[2] for i in v_for_neuron])
# pylab.show()

# Mean value of all membrane voltages
ticks_exc = len(v_exc) / len(pop_lsm_exc)
membrane_voltages_exc=v_exc[:,2].reshape((len(pop_lsm_exc),ticks_exc)).T

ticks_inh = len(v_inh) / len(pop_lsm_inh)
membrane_voltages_inh=v_inh[:,2].reshape((len(pop_lsm_inh),ticks_inh)).T

membrane_voltages=(membrane_voltages_exc.mean(axis=1)+membrane_voltages_inh.mean(axis=1))/2.0

pylab.plot(membrane_voltages)
pylab.title("Mean value - membrane voltages")
pylab.show()

sim.end()