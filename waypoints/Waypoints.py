import ipdb

import numpy as np
from matplotlib import pyplot as plt
import numpy.linalg as la

from scipy.sparse import csr_matrix
from synth_utils import deprecated

# Clean matrix  wrapper
def matrix(x):
    return np.atleast_2d(np.squeeze(np.array(x)))

@deprecated
class Waypoints:

    def __init__(self, bbox=[0,0,1,1], n=0, graph=None, NB=None, NL=None,
                 NS=None, freq=10, thresh=5):
        self.bbox = bbox    # [x1,y1,x2,y2]
        self.n = n
        self.wp = {}
        self.NB, self.NL, self.NS = NB, NL, NS
        self.freq, self.thresh = freq, thresh
        if graph is not None:
            self.sample_from_graph(graph)

    def sample_from_graph(self, graph):
        self.bbox = graph._get_bounding_box() # x1, y1, x2, y2
        # uniformly sample points in bbox
        if self.NB is not None:
            self.uniform_random(n=self.NB)
        # sample points along heavy edges (main roads)
        if self.NL is not None:
            heavy_edges = graph._get_heavy_edges(thresh=self.thresh)
            heavy_points =[(graph.G.node[e[0]]['pos'],graph.G.node[e[1]]['pos']) \
                           for e in heavy_edges]
            if len(heavy_points) > 1:
                self.gaussian_polyline(heavy_points,n=self.NL,tau=30)
        self._get_cp_trajs(graph,self.freq)

    # transform points from [0,1]^2 to bbox
    def shift_and_scale(self,D,bbox=None):
        if not bbox:
            bbox = self.bbox
        x_new = bbox[0] + D[:,0] * (bbox[2]-bbox[0])
        y_new = bbox[1] + D[:,1] * (bbox[3]-bbox[1])
        return np.vstack((x_new, y_new)).T

    # checks if point is in bounding box
    def in_box(self,p):
        if p[0] >= self.bbox[0] and p[0] <= self.bbox[2] and \
                p[1] >= self.bbox[1] and p[1] <= self.bbox[3]:
            return True
        return False

    # uniform (deterministic)
    def uniform(self,n):
        if n is None:
            n = self.n
        elif n == 0:
            return
        pass

    # uniform (random)
    def uniform_random(self,n=None):
        if n is None:
            n = self.n
        elif n == 0:
            return
        bbox = self.bbox
        samples = np.random.rand(n,2)
        self.wp['uniform_random'] = matrix(self.shift_and_scale(samples))

    # uniform (random) in a polygon
    def uniform_random_bbox(self,pop,bbox,n=None):
        if n is None:
            n = self.n
        elif n == 0:
            return
        waypoints = np.array([])
        while waypoints.shape[0] < n:
            if waypoints.size == 0:
                samples = n
            else:
                samples = 1
            # select bbox for each of n samples
            bbox_freq = np.random.multinomial(samples,pop/np.sum(pop))
            # for each bbox, uniformly sample
            for i,freq in enumerate(bbox_freq):
                if freq == 0:
                    continue
                x = self.shift_and_scale(np.random.rand(freq,2),bbox=bbox[i])
                x = np.array([p for p in x if self.in_box(p)])
                if x.size == 0:
                    continue
                if waypoints.size != 0:
                    waypoints = np.vstack((waypoints,x))
                else:
                    waypoints = x
        self.wp['uniform_rand_bbox'] = matrix(waypoints)

    # gaussian sampling along polyline
    def gaussian_polyline(self,p,n=None,log=False,bounded=True,tau=300):
        if n is None:
            n = self.n
        elif n == 0:
            return
        if log:
            dists = np.log([np.square(la.norm(np.array(points)[:-1,:] - \
                    np.array(points)[1:,:])) for points in p])
        else:
            dists = [np.square(la.norm(np.array(points)[:-1,:] - \
                    np.array(points)[1:,:])) for points in p]
        dists_sub = [np.sum(np.square(np.array(points)[:-1,:] - \
                np.array(points)[1:,:]),axis=1) for points in p]
        total = np.sum(dists)

        waypoints = np.array([])
        while waypoints.shape[0] < n:
            if waypoints.size == 0:
                samples = n
            else:
                samples = 1
            # select polyline for each of n samples
            road_freq = np.random.multinomial(samples,dists/total)
            # for each selected polyline, select segment for each of n samples
            seq_freq = [np.random.multinomial(j,dists_sub[i] / \
                    sum(dists_sub[i])) for i,j in enumerate(road_freq)]
            # for each segment, uniformly sample
            locs = np.random.random(samples)
            for i,freqs in enumerate(seq_freq):
                for j,freq in enumerate(freqs):
                    if freq == 0:
                        continue
                    for k in range(freq):
                        pos = np.random.random()
                        x = p[i][j] + (np.subtract(p[i][j], p[i][j+1])) * pos
                        dx = np.random.normal(scale=(self.bbox[2]-self.bbox[0])/tau)
                        dy = np.random.normal(scale=(self.bbox[3]-self.bbox[1])/tau)
                        x = x + np.array([dx,dy])
                        if not self.in_box(x):
                            continue
                        if waypoints.size != 0:
                            waypoints = np.vstack((waypoints,x))
                        else:
                            waypoints = x
        self.wp['gaussian_polyline'] = matrix(waypoints)

    # gaussian sampling around points
    def gaussian_points(self,p,n=None,bounded=True,tau=300):
        if n is None:
            n = self.n
        elif n == 0:
            return
        # select point for each of n samples
        waypoints = np.array([])
        while waypoints.shape[0] < n:
            if waypoints.size == 0:
                samples = n
            else:
                samples = 1
            points_ind = np.random.randint(0,len(p),samples)
            for ind in points_ind:
                dx = np.random.normal(scale=(self.bbox[2]-self.bbox[0])/tau)
                dy = np.random.normal(scale=(self.bbox[3]-self.bbox[1])/tau)
                x = p[ind] + np.array([dx,dy])
                if not self.in_box(x):
                    continue
                if waypoints.size != 0:
                    waypoints = np.vstack((waypoints,x))
                else:
                    waypoints = x
        self.wp['gaussian_points'] = matrix(waypoints)

    def draw(self):
        colors = 'rbmgcyk'

        # draw bounding box
        bbox = self.bbox
        plt.plot((bbox[0],bbox[0]),(bbox[1],bbox[3]),'k')
        plt.plot((bbox[2],bbox[2]),(bbox[1],bbox[3]),'k')
        plt.plot((bbox[0],bbox[2]),(bbox[1],bbox[1]),'k')
        plt.plot((bbox[0],bbox[2]),(bbox[3],bbox[3]),'k')

        # scatter waypoints
        for i,k in enumerate(self.wp):
            print k, self.wp[k].shape
            plt.scatter(self.wp[k][:,0],self.wp[k][:,1],label=k, \
                    color=colors[i],s=2)

        plt.title('Waypoints')
        plt.xlabel('lat')
        plt.ylabel('lon')
        plt.legend(loc='upper right')

    def show(self):
        self.draw()
        plt.show()

    def save(self,c):
        import pickle
        total = sum([len(v) for (k,v) in self.wp.iteritems()])
        pickle.dump(self.wp,open('%s/%s' % (c.DATA_DIR,
            c.WAYPOINTS_FILE % total),'w'))

    def load(self,c):
        import pickle
        return pickle.load(open('%s/%s' % (c.DATA_DIR,c.WAYPOINTS_FILE)))

    def closest_to_point(self, point, fast=False):
        """Find closest waypoint to a point (x,y)
        Note: fast is only available in Rectangle class"""
        min_dist = np.inf
        # TODO fast method not used here, update?
        if fast:
            x1,y1,x2,y2 = self.geometry
            res = self.partition[0]
            w, h = (x2-x1)/res[0], (y2-y1)/res[1]
            i = min(int(floor((point[0]-x1)/w)), res[0]-1)
            j = min(int(floor((point[1]-y1)/h)), res[1]-1)
            ids = self.partition[1][(i,j)]
        else:
            ids = self.wp.keys() #explore all ids
        for id in ids:
            x, y = self.wp[id][:,0], self.wp[id][:,1]
            d = np.linalg.norm([point[0]-x, point[1]-y], axis=0)
            d_min, i_min = np.min(d), np.argmin(d)
            if d_min < min_dist: min_dist, wp_id = d_min, (id,i_min)

        return wp_id


    def closest_to_line(self, directed_line, n, fast=False):
        """Find list of closest waypoints to a directed_line

        Parameters:
        ----------
        directed_line: (x1,y1,x2,y2)
        n: number of points to take on the line
        """
        x1,y1,x2,y2 = directed_line
        interp_x = np.linspace(x1,x2,num=n)
        interp_y = np.linspace(y1,y2,num=n)
        ids = [self.closest_to_point((x,y), fast) for (x,y) in zip(interp_x,interp_y)]
        ids_deduped = [ids[0]]
        ids_deduped.extend([y for (x,y) in zip(ids,ids[1:]) if x!=y])
        return ids_deduped


    def closest_to_polyline(self, polyline, n, fast=False):
        """Find list of closest waypoints to a directed polyline

        Parameters:
        ----------
        polyline: list of directed lines [(x1,y1,x2,y2)]
        n: number of points to take on each line of the polyline
        """
        ids = [self.closest_to_line(line, n, fast) for line in polyline]
        ids = [item for sublist in ids for item in sublist]
        ids_deduped = [ids[0]]
        ids_deduped.extend([y for (x,y) in zip(ids,ids[1:]) if x!=y])
        return ids_deduped


    def closest_to_path(self, graph, path, n, fast=False):
        """Find list of closest waypoints to a path in the graph

        Parameters:
        ----------
        graph: Graph object
        path: sequence of nodes in path
        n: number of points to take on each link of the path
        """
        polyline = []
        pos = [graph.node[x]['pos'] for x in path]
        for (i,x) in enumerate(pos[:-1]):
            x1, y1 = x
            x2, y2 = pos[i+1]
            polyline.append((x1,y1,x2,y2))
        return self.closest_to_polyline(polyline, n, fast)

    def get_wp_trajs(self, graph, routes, n, r_ids=None, fast=False, tol=1e-3):
        """Compute Waypoint trajectories and returns {path_id: wp_ids}, [(wp_traj, path_list, flow)]

        Parameters:
        ----------
        graph: Graph object with path flows in it
        n: number of points to take on each link of paths
        fast: if True do fast computation
        tol:

        Return value:
        ------------
        path_wps: dictionary of paths with >tol flow with wp trajectory associated {path_id: wp_ids}
        wp_trajs: list of waypoint trajectories with paths along this trajectory [(wp_traj, path_list, flow)]
        """
        if not r_ids:
            r_ids = xrange(len(routes))
        path_wps = [self.closest_to_path(graph, routes[r]['path'], n,
                                         fast=fast) for r in r_ids]
        wps = {}
        for value,key in enumerate(path_wps):
            wps.setdefault(tuple(key), []).append(value)
        return path_wps, wps

    def _get_cp_trajs(self, graph, n, fast=False, tol=1e-3):
        self.path_cps, self.cp_trajs = self.get_wp_trajs(graph.G,graph.routes,
                                                  n, fast=fast, tol=tol)

# Helper functions
# -------------------------------------
def to_np(X):
    return np.array(X).squeeze()

def to_sp(X):
    return csr_matrix((to_np(X.V),(to_np(X.I),to_np(X.J))), shape=X.size)

if __name__ == "__main__":
    rs = [0.25, 0.5, 0.75, 1, 1.5, 2, 2.5, 3, 3.5, 4, 6, 8]
    # rs = [0.1]

    import config as c

    for r in rs:
        # Official bounding box: -118.328299, 33.984601, -117.68132, 34.255881
        # w = Waypoints(bbox=[-118.328299, 33.984601, -117.68132, 34.255881])
        w = Waypoints(bbox=[-118.373284700001, 33.9309546999998,-117.6511386, 34.2584316999999])
        # w = Waypoints.load(c)
        # with open('%s/ATNT/la-laccids-smallpoly-uniq-locs.csv' % c.DATA_DIR) as f:
        #     points = f.readlines()
        # import ipdb
        # ipdb.set_trace()

        # uniform points
        w.uniform_random(n=150*r) # 1000
        print "Uniform random waypoints selected"

        # points along major roads
        import pickle
        roads = pickle.load(open('%s/%s' % (c.DATA_DIR,c.ROAD_FILE)))
        w.gaussian_polyline([y.points for (x,y) in roads],n=50*r) # 1000
        print "Polyline gaussian waypoints selected"

        # points around PEMS sensors
        # import csv
        # with open('%s/%s' % (c.DATA_DIR,c.SENSOR_FILE)) as csvfile:
        #     sensor_reader = csv.DictReader(csvfile)
        #     sensors = [(float(row['Longitude']),float(row['Latitude'])) for row \
        #             in sensor_reader]
        #     w.gaussian_points(sensors,n=0) # 1000
        # print "Point gaussian waypoints selected"

        # points by population
        import shapefile
        sf = shapefile.Reader("%s/workplace/tier1wgs84" % c.DATA_DIR)
        shapeRecords = sf.shapeRecords()
        TAZ_IDs = [x.record[3] for x in shapeRecords]
        areas = [x.record[1] for x in shapeRecords]
        pop20 = [x.record[4] for x in shapeRecords]
        emp20 = [x.record[6] for x in shapeRecords]
        pop35 = [x.record[8] for x in shapeRecords]
        bbox = [x.shape.bbox for x in shapeRecords]
        ind_bbox_filter = [(i,x) for (i,x) in enumerate(bbox) if w.in_box((x[0],x[1])) or w.in_box((x[2],x[3]))]
        ind, bbox_filter = zip(*ind_bbox_filter)
        ppl20_filter = [emp20[x] for x in ind] 
        w.uniform_random_bbox(ppl20_filter,bbox_filter,n=800*r) # 1000
        print "Bbox uniform waypoints selected"

        # w.save(c)

    # plot
    w.show()
