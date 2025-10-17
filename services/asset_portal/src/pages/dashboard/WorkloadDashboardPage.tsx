import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Progress,
  SimpleGrid,
  Stack,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr
} from '@chakra-ui/react';

const tasks = [
  { asset: 'Hero mech rig', due: 'Today', status: 'In review', progress: 80 },
  { asset: 'Hangar lighting pass', due: 'Tomorrow', status: 'Blocked', progress: 40 },
  { asset: 'FX sparks variant', due: 'Friday', status: 'In progress', progress: 55 }
];

const reviews = [
  { change: 'CL-4271', project: 'Odyssey', assigned: 'Morgan', due: '4h' },
  { change: 'CL-4269', project: 'Lego Racing', assigned: 'Priya', due: '1d' }
];

const WorkloadDashboardPage = () => (
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
);

export default WorkloadDashboardPage;
