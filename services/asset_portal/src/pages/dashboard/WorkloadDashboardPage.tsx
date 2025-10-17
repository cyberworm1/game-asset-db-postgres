import { useEffect, useState } from 'react';
import { isAxiosError } from 'axios';
import {
  Alert,
  AlertDescription,
  Badge,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Progress,
  SimpleGrid,
  Spinner,
  Stack,
  Stat,
  StatLabel,
  StatNumber,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr
} from '@chakra-ui/react';
import { fetchOpenCueSummary, OpenCueSummaryResponse } from '../../lib/rendering';

const tasks = [
  { asset: 'Hero mech rig', due: 'Today', status: 'In review', progress: 80 },
  { asset: 'Hangar lighting pass', due: 'Tomorrow', status: 'Blocked', progress: 40 },
  { asset: 'FX sparks variant', due: 'Friday', status: 'In progress', progress: 55 }
];

const reviews = [
  { change: 'CL-4271', project: 'Odyssey', assigned: 'Morgan', due: '4h' },
  { change: 'CL-4269', project: 'Lego Racing', assigned: 'Priya', due: '1d' }
];

const WorkloadDashboardPage = () => {
  const [renderSummary, setRenderSummary] = useState<OpenCueSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    const load = async () => {
      try {
        const data = await fetchOpenCueSummary();
        if (!ignore) {
          setRenderSummary(data);
        }
      } catch (err: unknown) {
        if (!ignore) {
          const message =
            isAxiosError(err) && err.response?.data?.detail
              ? err.response.data.detail
              : 'Unable to load render status.';
          setError(message);
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    };

    load();
    return () => {
      ignore = true;
    };
  }, []);

  const summaryGrid = (
    <Card>
      <CardHeader>
        <Heading size="md">Render queue</Heading>
      </CardHeader>
      <CardBody>
        {isLoading ? (
          <Stack direction="row" spacing={3} align="center">
            <Spinner size="sm" />
            <Text fontSize="sm">Fetching OpenCue status…</Text>
          </Stack>
        ) : error ? (
          <Alert status="warning" borderRadius="md">
            <AlertDescription fontSize="sm">{error}</AlertDescription>
          </Alert>
        ) : renderSummary ? (
          renderSummary.enabled && renderSummary.available ? (
            <Stack spacing={4}>
              <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
                {(
                  [
                    { label: 'Cued', value: renderSummary.summary.cued, color: 'purple' },
                    { label: 'Running', value: renderSummary.summary.running, color: 'blue' },
                    { label: 'Success', value: renderSummary.summary.success, color: 'green' },
                    { label: 'Fail', value: renderSummary.summary.fail, color: 'red' }
                  ] as const
                ).map((item) => (
                  <Stat key={item.label} borderRadius="lg" borderWidth="1px" padding={3}>
                    <StatLabel>{item.label}</StatLabel>
                    <StatNumber color={`${item.color}.500`}>{item.value}</StatNumber>
                  </Stat>
                ))}
              </SimpleGrid>
              <Text fontSize="xs" color="gray.500">
                Last updated {new Date(renderSummary.last_updated).toLocaleString()}
              </Text>
            </Stack>
          ) : (
            <Alert status="info" borderRadius="md">
              <AlertDescription fontSize="sm">
                {renderSummary.message ?? 'OpenCue integration is not enabled.'}
              </AlertDescription>
            </Alert>
          )
        ) : null}
      </CardBody>
    </Card>
  );

  return (
    <Stack spacing={6}>
      {summaryGrid}
      <SimpleGrid spacing={6} columns={{ base: 1, lg: 2 }}>
        <Card>
          <CardHeader>
            <Heading size="md">Assigned tasks</Heading>
          </CardHeader>
          <CardBody>
            <Stack spacing={4}>
              {tasks.map((task) => (
                <Stack key={task.asset} spacing={2}>
                  <Heading size="sm">{task.asset}</Heading>
                  <Stack direction="row" align="center" justify="space-between">
                    <Badge colorScheme="purple">Due {task.due}</Badge>
                    <Badge colorScheme={task.status === 'Blocked' ? 'red' : 'green'}>{task.status}</Badge>
                  </Stack>
                  <Progress value={task.progress} borderRadius="full" />
                </Stack>
              ))}
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <Heading size="md">Pending reviews</Heading>
          </CardHeader>
          <CardBody>
            <Table size="sm" variant="simple">
              <Thead>
                <Tr>
                  <Th>Changelist</Th>
                  <Th>Project</Th>
                  <Th>Assigned</Th>
                  <Th>Due</Th>
                </Tr>
              </Thead>
              <Tbody>
                {reviews.map((review) => (
                  <Tr key={review.change}>
                    <Td>{review.change}</Td>
                    <Td>{review.project}</Td>
                    <Td>{review.assigned}</Td>
                    <Td>{review.due}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </CardBody>
        </Card>
      </SimpleGrid>
    </Stack>
  );
};

export default WorkloadDashboardPage;
