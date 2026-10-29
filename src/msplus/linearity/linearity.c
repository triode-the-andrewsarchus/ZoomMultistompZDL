/* Output-stage diagnostic only; default Level=0 is silent.
 * Reviewed steps start at 1%, peak 0.0055, and never exceed DSP peak 0.55.
 * Require healthy calibrated loopback first; remove after measurement.
 */
#define MP_PROBE_PEAK 0.55f
#include "../common/triangle_probe.h"
