from __future__ import print_function, division
import numpy as np
import sys
import scipy.stats as stats
from mpi4py import MPI
try:
    from bipymc.demc import DeMcMpi
    from bipymc.samplers import DeMc
    from bipymc.dream import DreamMpi
    from bipymc.mc_plot import mc_plot
except:
    # add to path
    sys.path.append('../.')
    from bipymc.demc import DeMcMpi
    from bipymc.dream import DreamMpi
    from bipymc.mc_plot import mc_plot
np.random.seed(42)


def fit_line(mcmc_algo, comm):
    """!
    @brief Example data from http://dfm.io/emcee/current/user/line/
    For example/testing only.
    """
    # Choose the "true" parameters.
    m_true = -0.9594
    b_true = 4.294
    f_true = 0.534
    # Generate some synthetic data from the model.
    N = 50
    x = np.sort(10 * np.random.rand(N))
    yerr = 0.1 + 0.5 * np.random.rand(N)
    y = m_true * x + b_true
    y += np.abs(f_true * y) * np.random.randn(N)
    y += yerr * np.random.randn(N)


    # from http://dfm.io/emcee/current/user/line/
    def lnlike(theta, x, y, yerr):
        m, b, lnf = theta
        model = m * x + b
        inv_sigma2 = 1.0/(yerr**2 + model**2*np.exp(2*lnf))
        return -0.5*(np.sum((y-model)**2*inv_sigma2 - np.log(inv_sigma2)))

    def lnprior(theta):
        m, b, lnf = theta
        if -5.0 < m < 0.5 and 0.0 < b < 10.0 and -10.0 < lnf < 1.0:
            return 0.0
        return -np.inf

    def lnprob(theta, x, y, yerr):
        lp = lnprior(theta)
        if not np.isfinite(lp):
            return -np.inf
        return lp + lnlike(theta, x, y, yerr)


    # custom prior (ignore the unknown var term)
    def log_prior(theta):
        if (-50 < theta[0] < 50) and (-50 < theta[1] < 50):
            return 0.
        else:
            return -np.inf

    def model_fn(theta):
        return theta[0] + theta[1] * x

    def log_like_fn(theta, data):
        sigma = 1.0
        log_like = -0.5 * (np.sum((data - model_fn(theta)) ** 2 / sigma \
                - np.log(1./sigma)) + log_prior(theta))
        return log_like

    # === EXAMPLE 1 ===
    if comm.rank == 0: print("========== FIT LIN MODEL 1 ===========")
    theta_0 = np.array([4.0, -0.5])
    n_chains = comm.size*6
    my_mcmc = DreamMpi(log_like_fn, theta_0, n_chains=n_chains, mpi_comm=comm,
                      inflate=1e1, ln_kwargs={'data': y})
    my_mcmc.run_mcmc(500 * 100)

    # view results
    theta_est, sig_est, chain = my_mcmc.param_est(n_burn=10000)
    theta_est_, sig_est_, full_chain = my_mcmc.param_est(n_burn=0)
    if comm.rank == 0:
        print("Esimated params: %s" % str(theta_est))
        print("Estimated params sigma: %s " % str(sig_est))
        print("Acceptance fraction: %f" % my_mcmc.acceptance_fraction)
        # vis the parameter estimates
        mc_plot.plot_mcmc_params(chain,
                labels=["$y_0$", "m"],
                savefig='line_mcmc_ex.png',
                truths=[4.294, -0.9594])
        # vis the full chain
        mc_plot.plot_mcmc_indep_chains(full_chain, n_chains,
                labels=["$y_0$", "m"],
                savefig='lin_chain_ex.png',
                truths=[4.294, -0.9594], scatter=True)


    # === EXAMPLE 2 ===
    comm.Barrier()
    if comm.rank == 0: print("========== FIT LIN MODEL 2 ===========")
    theta_0 = np.array([-0.8, 4.5, 0.2])
    n_chains = comm.size*6
    my_mcmc = DreamMpi(lnprob, theta_0, n_chains=n_chains, mpi_comm=comm,
                      ln_kwargs={'x': x, 'y': y, 'yerr': yerr}, inflate=1e1)
    my_mcmc.run_mcmc(500 * 100)
    theta_est, sig_est, chain = my_mcmc.param_est(n_burn=10000)
    theta_est_, sig_est_, full_chain = my_mcmc.param_est(n_burn=0)
    if comm.rank == 0:
        print("Esimated params: %s" % str(theta_est))
        print("Estimated params sigma: %s " % str(sig_est))
        print("Acceptance fraction: %f" % my_mcmc.acceptance_fraction)
        # vis the parameter estimates
        mc_plot.plot_mcmc_params(chain,
                labels=["m", "$y_0$", "$\mathrm{ln}(f)$"],
                savefig='line_mcmc_ex_2.png',
                truths=[-0.9594, 4.294, np.log(f_true)])
        # vis the full chain
        mc_plot.plot_mcmc_indep_chains(full_chain, n_chains,
                labels=["m", "$y_0$", "$\mathrm{ln}(f)$"],
                savefig='lin_chain_ex_2.png',
                truths=[-0.9594, 4.294, np.log(f_true)],
                scatter=True)


def sample_gauss(mcmc_algo, comm):
    """! @brief Sample from a gaussian distribution """
    mu_gold, std_dev_gold = 5.0, 0.5

    def log_like_fn(theta, data=None):
        return np.log(stats.norm.pdf(theta[0],
                                     loc=mu_gold,
                                     scale=std_dev_gold)) - log_prior(theta)

    def log_prior(theta):
        if -100 < theta[0] < 100:
            return 0
        else:
            return -np.inf

    if comm.rank == 0: print("========== SAMPLE GAUSSI ===========")
    theta_0 = np.array([1.0])
    n_chains = comm.size*6
    my_mcmc = DreamMpi(log_like_fn, theta_0, n_chains=n_chains, mpi_comm=comm)
    my_mcmc.run_mcmc(4000)

    # view results
    theta_est, sig_est, chain = my_mcmc.param_est(n_burn=1000)
    theta_est_, sig_est_, full_chain = my_mcmc.param_est(n_burn=0)

    if comm.rank == 0:
        print("Esimated mu: %s" % str(theta_est))
        print("Estimated sigma: %s " % str(sig_est))
        print("Acceptance fraction: %f" % my_mcmc.acceptance_fraction)
        sys.stdout.flush()
        # vis the parameter estimates
        mc_plot.plot_mcmc_params(chain, ["$\mu$"], savefig='gauss_mu_mcmc_ex.png', truths=[5.0])
        # vis the full chain
        mc_plot.plot_mcmc_indep_chains(full_chain, n_chains, ["$\mu$"], savefig='gauss_mu_chain_ex.png',
                truths=[5.0], scatter=True)
    else:
        pass

def sample_bimodal_gauss(mcmc_algo, comm):
    mu_gold_a, std_dev_gold_a = -8.0, 1.0
    mu_gold_b, std_dev_gold_b = 10.0, 1.0

    def log_like_fn(theta, data=None):
        return np.log(
                (1 / 6.) * stats.norm.pdf(theta[0],
                               loc=mu_gold_a,
                               scale=std_dev_gold_a) +
                (5 / 6.) * stats.norm.pdf(theta[0],
                               loc=mu_gold_b,
                               scale=std_dev_gold_b)) \
                - log_prior(theta)

    def log_prior(theta):
        if (-100 < theta[0] < 100):
            return 0
        else:
            return -np.inf

    if comm.rank == 0: print("========== SAMPLE BIMODAL GAUSSI ===========")
    theta_0 = np.array([1.0])
    n_chains = comm.size*6
    my_mcmc = DreamMpi(log_like_fn, theta_0, n_chains=n_chains, varepsilon=1e-7, mpi_comm=comm, burnin_gen=0)
    my_mcmc.run_mcmc(1000 * n_chains)
    # my_mcmc = DeMcMpi(log_like_fn, theta_0, n_chains=comm.size*n_chains, varepsilon=1e-7, mpi_comm=comm, burnin_gen=0)

    #my_mcmc = DeMc(log_like_fn, n_chains=comm.size*n_chains, inflate=1e1, mpi_comm=comm, burnin_gen=0)
    #my_mcmc.run_mcmc(5000 * n_chains, theta_0)

    # view results
    theta_est, sig_est, chain = my_mcmc.param_est(n_burn=1000)
    theta_est_, sig_est_, full_chain = my_mcmc.param_est(n_burn=0)

    if comm.rank == 0:
        print("Esimated mu: %s" % str(theta_est))
        print("Estimated sigma: %s " % str(sig_est))
        print("Acceptance fraction: %f" % my_mcmc.acceptance_fraction)
        print("Expected Acceptance fraction: %f" % (0.36))
        sys.stdout.flush()
        # vis the parameter estimates
        mc_plot.plot_mcmc_params(chain, ["$\mu_b$"], savefig='gauss_bi_mu_mcmc_ex.png', truths=[(1/6.)*(-8.)+(5/6.)*(10.)])
        # vis the full chain
        mc_plot.plot_mcmc_indep_chains(full_chain, n_chains, ["$\mu_b$"],
                savefig='gauss_bi_mu_chain_ex.png',
                truths=[(1/6.)*(-8.)+(5/6.)*(10.)], scatter=True)
    else:
        pass


if __name__ == "__main__":
    comm = MPI.COMM_WORLD
    print("Hello From Rank: ", comm.rank)
    sys.stdout.flush()
    sample_gauss("DE-MC", comm)
    sample_bimodal_gauss("DREAM", comm)
    fit_line("DE-MC-MPI", comm)
