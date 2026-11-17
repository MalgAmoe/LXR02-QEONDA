#include "Soundengine/DSPAudio/MainCompressor.h"
#include <math.h>
#include <string.h>
#include "Parameters.h"
_Static_assert(MASTER_COMP_THRESHOLD==302 && MASTER_COMP_RATIO==303 &&
               MASTER_COMP_ATTACK==304 && MASTER_COMP_RELEASE==305, "compressor IDs");
#ifndef LXR_HOST_TEST
#include "stm32f7xx.h"
#endif
/* Independently designed conventional peak compressor; no circuit-model code.
 * 221 samples = 5.007ms at 44140Hz. Only control coefficients and bypass mix
 * ramp; the signal detector/curve remain full-rate with no extra gain lag. */
static volatile uint8_t compTargets[4] = {36, 0, 17, 20};
static struct {
    float envelope, gain, makeup, makeupGoal;
    float attack, release, threshold, slope;
    float goalThreshold, goalSlope, dThreshold, dSlope;
    float goalAttack, goalRelease, dAttack, dRelease;
    float wet, wetGoal, dWet;
    unsigned curveRamp, wetRamp;
    uint8_t previous[4], initialized;
} comp;
void MainCompressor_setParameter(uint16_t parameter, uint8_t value)
{
    static const uint8_t limits[4] = {48,19,30,34};
    if (parameter < 302 || parameter > 305) return;
    unsigned i=parameter-302;
    compTargets[i]=value>limits[i]?limits[i]:value;
}
void MainCompressor_setControls(const uint8_t controls[4])
{
    static const uint8_t limits[4] = {48,19,30,34};
    uint8_t target[4];
    for (unsigned i=0;i<4;++i)
        target[i]=controls[i]>limits[i]?limits[i]:controls[i];
#ifndef LXR_HOST_TEST
    uint32_t saved=__get_PRIMASK();
    __disable_irq();
#endif
    /* Only four byte stores are masked; no coefficient or UI work here. */
    for (unsigned i=0;i<4;++i) compTargets[i]=target[i];
#ifndef LXR_HOST_TEST
    __set_PRIMASK(saved);
#endif
}
static float reduction(float db)
{
    float d=db-comp.threshold;
    if (d <= -3.f) return 0.f;
    if (d >= 3.f) return comp.slope*d;
    return comp.slope*(d+3.f)*(d+3.f)/12.f;
}
unsigned MainCompressor_beginBlock(void)
{
#ifndef LXR_HOST_TEST
    uint32_t saved=__get_PRIMASK();
    __disable_irq();
#endif
    uint8_t p[4];
    for (unsigned i=0;i<4;++i) p[i]=compTargets[i];
#ifndef LXR_HOST_TEST
    __set_PRIMASK(saved);
#endif
    unsigned changed=!comp.initialized;
    for (unsigned i=0;i<4;++i) changed |= p[i]!=comp.previous[i];
    if (!comp.initialized) { comp.gain=1.f; comp.makeup=1.f; }
    if (changed) {
        /* Ratio1 drains using the last active curve and makeup target. */
        if (p[1]) {
            comp.goalThreshold=(float)p[0]-48.f;
            comp.goalSlope=1.f-1.f/(1.f+p[1]);
            if (comp.wet==0.f) {
                comp.threshold=comp.goalThreshold; comp.slope=comp.goalSlope;
            }
            comp.dThreshold=(comp.goalThreshold-comp.threshold)/221.f;
            comp.dSlope=(comp.goalSlope-comp.slope)/221.f;
            comp.curveRamp=221;
        }
        float wetGoal=p[1]?1.f:0.f;
        if (wetGoal!=comp.wetGoal) {
            comp.wetGoal=wetGoal;
            comp.dWet=(wetGoal-comp.wet)/221.f;
            comp.wetRamp=221;
        }
        float attackMs=0.1f*powf(1000.f,p[2]/30.f);
        float releaseMs=10.f*powf(50.f,p[3]/34.f);
        comp.goalAttack=expf(-1000.f/(44140.f*attackMs));
        comp.goalRelease=expf(-1000.f/(44140.f*releaseMs));
        if (comp.wet==0.f) {
            comp.attack=comp.goalAttack; comp.release=comp.goalRelease;
        }
        comp.dAttack=(comp.goalAttack-comp.attack)/221.f;
        comp.dRelease=(comp.goalRelease-comp.release)/221.f;
        if (!p[1]) comp.curveRamp=0; /* Freeze the last active configuration. */
        float d=-comp.goalThreshold;
        float r=d<=-3.f?0.f:d>=3.f?comp.goalSlope*d:
                comp.goalSlope*(d+3.f)*(d+3.f)/12.f;
        // Gradually increasing margin below full 0 dBFS reference compensation.
        float makeupDb=r-4.f*r/(r+12.f);
        if (p[1]) comp.makeupGoal=powf(10.f,makeupDb/20.f);
        for (unsigned i=0;i<4;++i) comp.previous[i]=p[i];
        comp.initialized=1;
    }
    return p[1] || comp.wetRamp || comp.wet>0.f;
}
/* Binary32 range reduction; independent analytic polynomials, no tables or
 * library log/exp calls in the sample path. ln(m)=2 atanh((m-1)/(m+1)).
 * m in [1,2), |t| <= 1/3; six odd terms. exp(r) uses degree six,
 * r in [0,ln(2)]. The control path still uses libm once per change. */
static float envelopeDb(float e)
{
    if (e<1.e-20f) e=1.e-20f;
    uint32_t bits; memcpy(&bits,&e,4);
    int exponent=(int)(bits>>23)-127;
    bits=(bits&0x7fffffu)|0x3f800000u;
    float m; memcpy(&m,&bits,4);
    float t=(m-1.f)/(m+1.f), z=t*t;
    float l=2.f*t*(1.f+z*(1.f/3.f+z*(1.f/5.f+z*(1.f/7.f+
                      z*(1.f/9.f+z/11.f)))));
    return 6.020599913f*exponent+8.685889638f*l;
}
static float attenuation(float db)
{
    float x=-db*0.166096405f; /* dB -> binary exponent */
    if (x< -126.f) x= -126.f;
    int n=(int)x;
    if ((float)n>x) --n;
    float r=(x-n)*0.693147181f;
    float p=1.f+r*(1.f+r*(0.5f+r*(1.f/6.f+r*(1.f/24.f+
                        r*(1.f/120.f+r/720.f)))));
    uint32_t bits=(uint32_t)(n+127)<<23;
    float scale; memcpy(&scale,&bits,4);
    return scale*p;
}
void MainCompressor_processPair(float x[2])
{
    if (comp.curveRamp) {
        comp.threshold+=comp.dThreshold; comp.slope+=comp.dSlope;
        comp.attack+=comp.dAttack; comp.release+=comp.dRelease;
        if (!--comp.curveRamp) {
            comp.threshold=comp.goalThreshold; comp.slope=comp.goalSlope;
            comp.attack=comp.goalAttack; comp.release=comp.goalRelease;
        }
    }
    if (comp.wetRamp) {
        comp.wet+=comp.dWet;
        if (!--comp.wetRamp) comp.wet=comp.wetGoal;
    }
    if (comp.wet==0.f) {
        /* Exact settled bypass; render may still call us for this block. */
        comp.envelope=0.f; comp.gain=comp.makeup=1.f;
        comp.curveRamp=0;
        return;
    }
    float peak=fmaxf(fabsf(x[0]),fabsf(x[1]))*(1.f/32768.f);
    float a=peak>comp.envelope?comp.attack:comp.release;
    comp.envelope=peak+a*(comp.envelope-peak);
    comp.gain=attenuation(reduction(envelopeDb(comp.envelope)));
    /* 20ms fixed makeup smoothing, independent of program level (not AGC). */
    comp.makeup+=0.001132132f*(comp.makeupGoal-comp.makeup);
    float g=1.f+comp.wet*(comp.gain*comp.makeup-1.f);
    x[0]*=g; x[1]*=g;
}
