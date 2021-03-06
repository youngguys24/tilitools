import numpy as np
from numba import autojit
from functools import partial

from utils_optimize import min_subgradient_descent
from utils import profile

class LpOcSvmPrimalSGD:
    """ Lp-norm regularized primal one-class support vector machine.

    """
    PRECISION = 1e-3 # important: effects the threshold, support vectors and speed!
    w = None     # (vector) parameter vector
    nu = 1.0	 # (scalar) the regularization constant 1/n <= nu <= 1
    pnorm = 2.0  # (scalar) p-norm
    threshold = 0.0	 # (scalar) the optimized threshold (rho)
    outliers = None  # (vector) indices of real outliers in the training sample

    def __init__(self, pnorm=2., nu=1.0):
        self.nu = nu
        self.pnorm = pnorm
        print('Creating new primal lp (p={0}) one-class svm with C=1/(n*nu) (nu={1}).'.format(pnorm, nu))

    @profile
    def fit(self, X, max_iter=1000000, prec=1e-6, step_rate=0.01, step_method=1):
        # number of training examples
        feats, n = X.shape
        x0 = np.zeros(feats+1)
        x0[1:] = np.mean(X, axis=1)
        # x0[0] = np.min(np.median(X, axis=0))

        # x0 = np.random.randn(feats+1)
        xstar, obj, iter = min_subgradient_descent(x0,
                                                   partial(fun, data=X, p=self.pnorm, nu=self.nu),
                                                   partial(grad, data=X, p=self.pnorm, nu=self.nu),
                                                   max_iter, prec, step_rate, step_method=step_method)
        self.threshold = xstar[0]
        self.w = xstar[1:]
        scores = self.apply(X)
        self.outliers = np.where(scores < 0.)[0]
        print('---------------------------------------------------------------')
        print('Stats:')
        print('Number of samples: {0}, nu: {1}; C: ~{2:1.2f}; %Outliers: {3:3.2f}%.'
              .format(n, self.nu, 1./(self.nu*n),np.float(self.outliers.size) / np.float(n) * 100.0))
        print('Hyperparameter nu ({0}) is an upper bound on the fraction of outliers ({0} >= {1:3.2f}%). '
              .format(self.nu, np.float(self.outliers.size) / np.float(n) * 100.0))
        print('Threshold is {0}'.format(self.threshold))
        print('Objective is {0}'.format(fun(xstar, X, self.pnorm, self.nu)))
        print('Iterations {0}'.format(iter))
        print('---------------------------------------------------------------')


    def get_threshold(self):
        return self.threshold

    def get_outliers(self):
        return self.outliers

    def apply(self, X):
        return self.w.T.dot(X) - self.threshold


def fun2(x, data, p, nu):
    feat, n = data.shape
    C = 1./(np.float(n)*nu)
    w = x[1:]
    rho = x[0]
    slacks = rho - w.T.dot(data)
    slacks[slacks < 0.] = 0.
    return 0.5*w.T.dot(w) - rho + C*np.sum(slacks)


def grad2(x, data, p, nu):
    feats, n = data.shape
    C = 1./(np.float(n)*nu)
    w = x[1:]
    rho = x[0]
    slacks = rho - w.T.dot(data)
    inds = np.where(slacks >= 0.0)[0]

    grad = np.zeros(feats+1)
    grad[0] = -1. + C * np.float(inds.size)
    grad[1:] = w - C * np.sum(data[:, inds])
    return grad


@autojit(nopython=True)
def fun(x, data, p, nu):
    feat, n = data.shape
    w = x[1:]
    rho = x[0]
    pnorm = np.sum(np.abs(w)**p)**(1./p)
    # for nopython mode
    slacks = 0.0
    for i in range(n):
        foo = rho
        for j in range(feat):
            foo -= w[j]*data[j, i]
        if foo > 0.:
            slacks += foo
    return pnorm - rho + 1./(np.float(n)*nu) * slacks


@autojit(nopython=True)
def grad(x, data, p, nu):
    feats, n = data.shape
    C = 1./(np.float(n)*nu)
    w = x[1:]
    rho = x[0]

    pnorm1 = np.sum(np.abs(w)**p)**((p-1.)/p)
    grad_pnorm = (w*np.abs(w)**(p-2.)) / pnorm1

    sum_rho = 0.0
    sum_data = np.zeros(feats)
    for i in range(n):
        foo = rho
        for j in range(feats):
            foo -= w[j]*data[j, i]
        if foo > 0.:
            sum_rho += 1.
            sum_data += data[:, i]

    grad = np.zeros(feats+1)
    grad[0] = -1. + C * sum_rho
    grad[1:] = grad_pnorm - C * sum_data
    return grad