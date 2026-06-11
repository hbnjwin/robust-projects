using UnityEngine;
using UnityEngine.AI;

public class EnemyAI : MonoBehaviour
{
    private NavMeshAgent agent;
    private Transform[] patrolPoints;
    private int currentPoint = 0;

    void Start()
    {
        agent = GetComponent<NavMeshAgent>();
    }

    void Update()
    {
        if (!agent.pathPending && agent.remainingDistance < 0.5f)
        {
            currentPoint = (currentPoint + 1) % patrolPoints.Length;
            agent.SetDestination(patrolPoints[currentPoint].position);
            // BUG: no handling for when agent is stuck at corner
        }
    }
}
