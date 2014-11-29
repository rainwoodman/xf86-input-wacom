#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include "xf86Wacom.h"
#include "Xwacom.h"
#include "wcmFilter.h"
#include "wcmTouchFilter.h"
#include <xkbsrv.h>
#include <xf86_OSproc.h>

static int mybsearch(int * array, int size, int value);

WacomCalibrationGridPtr wcmNewCalibrationGrid(int devsizex, int devsizey, int nx, int ny) {
        WacomCalibrationGrid * grid = calloc(1, sizeof(WacomCalibrationGrid));
        int i, j;
        grid->DevGrid[0] = malloc(sizeof(int) * nx);
        grid->DevGrid[1]= malloc(sizeof(int) * ny);
        grid->UnitCoord[0] = calloc((nx + 2) * (ny + 2), sizeof(float));                
        grid->UnitCoord[1] = calloc((nx + 2) * (ny + 2), sizeof(float));                
        grid->size[0] = nx;
        grid->size[1] = ny;
        grid->nx = nx;
        grid->ny = ny;
        for(i = 0; i < nx; i ++) {
                grid->DevGrid[0][i] = devsizex * (long) (i ) / (nx - 1);
        }
        for(i = 0; i < ny; i ++) {
                grid->DevGrid[1][i] = devsizey * (long) (i ) / (ny - 1);
        }
        for(i = 0; i < nx + 2; i ++) {
                grid->UnitCoord[1][i * (ny + 2) + 0] = 0.0;
                grid->UnitCoord[1][i * (ny + 2) + ny + 1] = 1.0;
        }
        for(i = 0; i < ny + 2; i ++) {
                grid->UnitCoord[0][0 * (ny + 2) + i] = 0.0;
                grid->UnitCoord[0][(nx + 1) * (ny + 2) + i] = 1.0;
        }
        for(j = 0; j < ny; j ++) {
                for(i = 0; i < nx; i ++) {
                        wcmCalibrationGridSetData(grid, i, j, 1.0 * i / (nx - 1), 1.0 * j / (ny - 1));
                }
        }
        return grid;
}

WacomCalibrationGridPtr wcmNewCalibrationGridFromString(int devsizex, int devsizey, char * data) {
	int xgrid[1000];
	int ygrid[1000];
	int nx = 0;
	int ny = 0;
	char *p, *q;
	char * item;
	int STATE = 0;
        WacomCalibrationGrid * grid = NULL;
	int i = 0, j = 0, d = 0;
	float value[2];

	for (q = p = data; *p; p++) {
		switch(STATE) {
			case 0:
				if(*p == ',' || *p == ';') {
					item = strndup(q, p - q);
					q = p + 1;
					xgrid[nx] = atoi(item);
					nx ++;
					free(item);
				}
				if(*p == ';') {
					STATE ++;
				}
				break;
			case 1:
				if(*p == ',' || *p == ';') {
					item = strndup(q, p - q);
					q = p + 1;
					ygrid[ny] = atoi(item);
					ny ++;
					free(item);
				}
				if(*p == ';') {
					/* grid is loaded, ok to allocate the calib object */
					grid = wcmNewCalibrationGrid(devsizex, devsizey, nx, ny);
					memcpy(grid->DevGrid[0], xgrid, sizeof(int) * nx);
					memcpy(grid->DevGrid[1], ygrid, sizeof(int) * ny);
					STATE ++;
				}
				break;
				/* the actual unit coord follows, in x-fast ordering */
			case 2:
				if(*p == ',' || *p == ';') {
					item = strndup(q, p - q);
					q = p + 1;
					value[d] = atof(item);
					d ++;
					free(item);
				}
				if(d == 2) {
					wcmCalibrationGridSetData(grid, i, j, value[0], value[1]);
					d = 0;
					i ++;
				}
				if(i == nx) {
					j++;
					i = 0;
				}
				if(j == ny) {
					goto done;
				}
				break;
		}
	}
done:
	return grid;
}

int wcmCalibrationGridSetData(WacomCalibrationGrid * grid, int bx, int by, float x, float y) {
        int stride = grid->ny + 2;
        if(bx < 0 || bx > grid->nx - 1) {
                return -1;
        }
        if(by < 0 || by > grid->ny - 1) {
                return -1;
        }
        bx ++;
        by ++;
	if(bx == 1) {
		grid->UnitCoord[1][(bx - 1)* stride + by] = y;
	}
	if(bx == grid->nx) {
		grid->UnitCoord[1][(bx + 1)* stride + by] = y;
	}
	if(by == 1) {
		grid->UnitCoord[0][bx * stride + by - 1] = x;
	}
	if(by == grid->ny) {
		grid->UnitCoord[0][bx * stride + by + 1] = x;
	}
        grid->UnitCoord[0][bx * stride + by] = x;
        grid->UnitCoord[1][bx * stride + by] = y;
        return 0;
};
void wcmFreeCalibrationGrid(WacomCalibrationGrid * grid) {
        int d;
        for(d = 0; d < 2; d++) {
                free(grid->DevGrid[d]);
                free(grid->UnitCoord[d]);
        }
        free(grid);
}
void wcmDevCoordToUnitCoord(WacomCalibrationGridPtr grid, int devx, int devy, float *unitx, float * unity) {
        int binxy[2];
        int devxy[2] = {devx, devy};
        float f11, f12, f21, f22;
        float u[2], v[2];
        float unitxy[2];
        int d;
        int bx, by, stride;

        for(d = 0; d < 2; d ++) {
                int b = mybsearch(grid->DevGrid[d], grid->size[d], devxy[d]);
                binxy[d] = b;
                if(binxy[d] >= 0 && binxy[d] < grid->size[d] - 1) {
                        int dx = grid->DevGrid[d][b + 1] - grid->DevGrid[d][b];
                        u[d] = 1.0 * (devxy[d] - grid->DevGrid[d][b]) / dx;
                        v[d] = 1.0 * (grid->DevGrid[d][b + 1] - devxy[d]) / dx;
                } else {
                        u[d] = 1.0;
                        v[d] = 0.0;
                }
        }
        /* adjust to the array index in UnitCoord*/
        bx = binxy[0] + 1;
        by = binxy[1] + 1;
        stride = grid->ny + 2;
        for(d = 0; d < 2; d++) {
                f11 = grid->UnitCoord[d][bx * stride + by];
                f12 = grid->UnitCoord[d][bx * stride + by + 1];
                f21 = grid->UnitCoord[d][(bx + 1) * stride + by];
                f22 = grid->UnitCoord[d][(bx + 1) * stride + by + 1];
                /**
                   *  x: u0     v0
                   * y
                   * u1 f11    f21
                   *         x
                   *
                    * v1 f12    f22
                   *
                   * */
                unitxy[d] = v[0]*v[1] * f11 + v[1]*u[0] * f21 
                          + v[0]*u[1] * f12 + u[0]*u[1] * f22;
                printf("%d %d %d f(%g %g %g %g) u(%g %g) v(%g %g)\n", d, bx, by, f11, f12, f21, f22, u[0], u[1], v[0], v[1]);
        }
        *unitx = unitxy[0];
        *unity = unitxy[1];
}
/*
 * returns:
 *   index such that array[index] <= value < array[index + 1]
 * */
static int mybsearch(int * array, int size, int value) {
        int left = 0;
        int right;

        if(size == 0) return -1;
        right = size - 1;
        if (value < array[left] ) {
                return -1;
        }
        if (value >= array[right]) {
                return right;
        }

        /* left <= value < right)*/
        while(right - left > 1) {
                int mid = left + ((right - left + 1) >> 1);
        //        printf("%d %d %d\n", left, mid, right);
                int foo = array[mid];
                if (value >= foo) {
                        left = mid;
                } else {
                        right = mid;
                }
        }
        return left;
}

void wcmInfoCalibrationGrid(WacomCalibrationGridPtr grid) {
        int i, j;
	char * buf = NULL;
	char * p;
	if(grid == NULL) {
		xf86Msg(X_INFO, "wacom CalibrationGrid is disabled.\n");
		return;
	}
	buf = malloc(grid->nx * 9);
	p = buf;
        for(i = 0; i < grid->nx; i ++) {
                p += sprintf(p, "%d ", grid->DevGrid[0][i]);
        }
	xf86Msg(X_INFO, "wacom CalibrationGrid X: %s\n", buf);
	free(buf);

	buf = malloc(grid->ny * 9);
	p = buf;
        for(j = 0; j < grid->ny; j ++) {
                p += sprintf(p, "%d ", grid->DevGrid[1][j]);
        }
	xf86Msg(X_INFO, "wacom CalibrationGrid Y: %s\n", buf);
	free(buf);
	
        for(j = 0; j < grid->ny + 2; j ++) {
		buf = malloc(grid->nx * 20);
		p = buf;
                for(i = 0; i < grid->nx + 2; i ++) {
                        int l = i * (grid->ny + 2) + j;
                        p += sprintf(p, "%0.2f %0.2f, ", grid->UnitCoord[0][l], grid->UnitCoord[1][l]);
                }
		xf86Msg(X_INFO, "wacom CalibrationGrid Data: %s\n", buf);
		free(buf);
        }        
}

#if 0
void test(WacomCalibrationGrid * grid, int devx, int devy) {
        float unitx, unity;
        wcmDevCoordToUnitCoord(grid, devx, devy, &unitx, &unity);
        printf("%d %d => %g %g\n", devx, devy, unitx, unity);
}

int main() {
        WacomCalibrationGrid grid;
        wcmCalibrationGridInit(&grid, 50, 40, 6, 5);
        int i, j;
        for(i = 0; i < grid.nx; i ++) {
                printf("%d ", grid.DevGrid[0][i]);
        }
        printf("\n");
        for(j = 0; j < grid.ny; j ++) {
                printf("%d ", grid.DevGrid[1][j]);
        }
        printf("\n");
        for(j = 0; j < grid.ny + 2; j ++) {
                for(i = 0; i < grid.nx + 2; i ++) {
                        int l = i * (grid.ny + 2) + j;
                        printf("%0.2f %0.2f, ", grid.UnitCoord[0][l], grid.UnitCoord[1][l]);
                }
                printf("\n");
        }        
        test(&grid, 0, 0);
        test(&grid, 10, 20);
        test(&grid, 11, 20);
        test(&grid, 20, 20);
        test(&grid, 50, 40);
        test(&grid, 100, 80);
        return 0;
}
#endif

/* vim: set noexpandtab tabstop=8 shiftwidth=8: */
